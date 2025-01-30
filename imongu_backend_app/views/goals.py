from rest_framework import status
from imongu_backend_app.models import User,company,employee,Goal,goal_owners, okr,owners,key_results,result_owner,update_key_results,team_Table,Parents,team_employees
from imongu_backend_app.Serializers import GoalSerializers, okrserializers,key_resultsserializers,update_keyresultsserializers,OKRSerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
import uuid
from dateutil import parser as date_parser
from django.db.models import Avg
import json
from imongu_backend_app.utils.owners import *
from imongu_backend_app.utils.helper import *
from imongu_backend_app.utils.notification import *
from imongu_backend_app.utils.jira import *
from datetime import datetime, timedelta
from rest_framework.views import APIView
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, validate_feature_activity_access
from integrations.utils.trello import *
from integrations.models import AsanaConnection
from integrations.utils.asana_utils import *
from django.conf import settings

class goal_deatils(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Count"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
 
        goal_id=str(uuid.uuid4())
        company_id=request.data.get('company_id')
        session=request.data.get('session')
        title=request.data.get('title','')
        description=request.data.get('description','')
        team_ids = request.data.get('team_id',[])
        p_id = request.data.get('parent','')  # p_id can be goal id, okr id, key_result id
        parent_type = request.data.get('parent_type','') # parent_type can be goal , okr , key_result 
        company_obj=company.objects.get(company_id=company_id)

        if p_id and parent_type:
            # parent_id is a unique key of Parents table which have parent like goal , okr , key_result
            parent_id = save_parents(p_id,parent_type,"goal")
        else:
            parent_id=None

        goal_instanse=Goal(
            goal_id=goal_id,
            company_id=company_obj,
            session=session,
            parent_id=parent_id,
            title=title,
            description=description,
        )
        goal_instanse.save()
        user_ids = request.data.get('user_id',[])
        goal_obj=Goal.objects.get(goal_id=goal_id)
        for user_id in user_ids:
            user=User.objects.get(user_id=user_id)
            goal_owners_instance=goal_owners(
                goal_owner_id=str(uuid.uuid4()),
                user_id=user,
                goal_id=goal_obj,
            )
            goal_owners_instance.save()

        # for assign goal owner to team
        for team_id in team_ids:
            team=team_Table.objects.get(team_id=team_id)
            goal_owners_instance=goal_owners(
                goal_owner_id=str(uuid.uuid4()),
                team_id=team,
                goal_id=goal_obj,
            )
            goal_owners_instance.save()
        serilizer=GoalSerializers(goal_instanse)
        if login_user_id:
            user = User.objects.get(user_id=login_user_id)
            message = user.username + " created the goal "
            changes = {}
            changes['goal_id'] = str(goal_id)
            employee_user_ids = []
            for team_id in team_ids:
                employee_ids = team_employees.objects.filter(team_id=team_id).values_list('user_id_id', flat=True)
                employee_user_ids.extend(employee_ids)
            save_notification(company_id , message,user, "goal", title = goal_instanse.title , changes = changes)

        # creating jira epiq with goal
        if validate_jira(company_id):
            epic_key = create_epic(title, description , company_id)
            if epic_key:
                goal_instanse.epic_key = epic_key
                goal_instanse.save()
        api_key, token = get_trello_credentials(user_id)
        if api_key and token:
            board_id = trello_create_board(user_id,title)
            if board_id:
                goal_instanse.trello_board_id = board_id
                goal_instanse.save()
                try:
                    setup_webhooks(api_key, token, request)
                except Exception as e:
                    logger.error(f"Failed to set up Trello webhook: {e}")
                    return Response({"error": "Failed to set up Trello webhook"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            asana_connection = AsanaConnection.objects.get(user=user_id)
        except (AsanaConnection.DoesNotExist):
            asana_connection = None

        if asana_connection:
            asana_access_token = asana_connection.access_token
            workspaces = get_workspaces(asana_access_token)

            if workspaces:
                workspace_id = workspaces[0]["gid"]  
                teams = get_teams_in_workspace(asana_access_token, workspace_id)
                if teams:
                    team_id = teams[0]["gid"] 
                    asana_project_id = create_asana_project(
                        asana_access_token, title, workspace_id, description, team_id)
                if asana_project_id:
                    goal_instanse.asana_project_id = asana_project_id
                    goal_instanse.save()
                    sections = get_project_sections(asana_project_id, asana_access_token)
                    if sections:
                        for section in sections.get("data", []):
                            if section["name"] == "Untitled Section":
                                print("untitled")  
                                delete_section(section["gid"], asana_access_token) 

                    to_do_section = create_asana_section(asana_access_token, asana_project_id, "To Do")
                    doing_section = create_asana_section(asana_access_token, asana_project_id, "Doing")
                    done_section = create_asana_section(asana_access_token, asana_project_id, "Done")

                    if not all([to_do_section, doing_section, done_section]):
                        logger.error("One or more sections could not be created. Check the logs for details.")
                    else:
                        logger.info("All sections created successfully.")
                    try:
                        callback_url = settings.ASANA_CALLBACK_URL 
                        create_asana_webhook(asana_access_token, asana_project_id, callback_url)
                    except Exception as e:
                        logger.error(f"Error setting up Asana webhook: {e}")
                        return Response(
                            {"error": "Failed to set up Asana webhook"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

        return Response(serilizer.data,status=status.HTTP_200_OK)

    def get(self,request):
        try:
            user_id = GetUserId.get_user_id(request)
            company_id = request.query_params.get('company_id')

            if not company_id:
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            all_goals=[]
            session=request.query_params.get('session')
            fields = request.query_params.get('fields')
            if fields is not None:
                field_dict = json.loads(fields)
            else:
                field_dict = {}
            goal_name = field_dict.get('goal_name')
            goal_owner_user_ids = field_dict.get('goal_owner', {}).get('user_ids', [])
            goal_owner_team_ids = field_dict.get('goal_owner',{}).get('team_ids',[])
            okr_name = field_dict.get('okr_name')
            okr_owner_user_ids = field_dict.get('okr_owner',{}).get('user_ids',[])
            okr_owner_team_ids = field_dict.get('okr_owner',{}).get('team_ids',[])
            progress_equal_to = field_dict.get('progress',{}).get('equal_to')
            progress_not_equal_to = field_dict.get('progress',{}).get('not_equal_to')
            progress_less_than = field_dict.get('progress',{}).get('less_than')
            progress_greater_than = field_dict.get('progress',{}).get('greater_than')
            last_updated_never = field_dict.get('last_updated',{}).get('never')
            last_updated_before = field_dict.get('last_updated',{}).get('before')
            last_updated_after = field_dict.get('last_updated',{}).get('after')
            last_updated_between = field_dict.get('last_updated',{}).get('between')

            queryset=Goal.objects.filter(company_id=company_id, is_deleted=False).prefetch_related( "goal_owners").order_by('-created_at')
            if session:
                goal_objs=queryset.filter(session=session)
            else:
                goal_objs=queryset

            # Apply goal_name filter
            if goal_name:
                goal_objs = goal_objs.filter(title__icontains=goal_name)

            # Apply goal_owner filter
            if goal_owner_user_ids:
                goal_objs = goal_objs.filter( goal_owners__user_id__in=goal_owner_user_ids)

            if goal_owner_team_ids:
                goal_objs = goal_objs.filter(goal_owners__team_id__in=goal_owner_team_ids)

            # Apply okr_name filter
            if okr_name:
                goal_objs = goal_objs.filter(okr__title__icontains=okr_name)

            # Apply okr_owner filter
            if okr_owner_user_ids :
                goal_objs = goal_objs.filter(okr__owners__user_id__in=okr_owner_user_ids)

            if okr_owner_team_ids:
                goal_objs = goal_objs.filter(okr__owners__team_id__in=okr_owner_team_ids)

            # Add filters based on date parameters
            if last_updated_before:
                goal_objs = goal_objs.filter(okr__key_results__update_key_results__changed_at__lt=last_updated_before)

            if last_updated_after:
                goal_objs = goal_objs.filter(okr__key_results__update_key_results__changed_at__gt=last_updated_after)

            if last_updated_between:
                start_date, end_date = last_updated_between.split(',')
                goal_objs = goal_objs.filter(okr__key_results__update_key_results__changed_at__range=(start_date, end_date))

            if goal_objs:
                goal_objs_data = GoalSerializers(goal_objs, many=True, context={'user_id': int(user_id)})
                goal_ids_in_data = [goal['goal_id'] for goal in goal_objs_data.data if goal is not None]
                left_goals = goal_objs.exclude(goal_id__in=goal_ids_in_data)
                
                # check if current user present in objective owner then add it to shared goals
                shared_goal = check_shared_okr(left_goals, user_id)
                all_goals.extend(shared_goal)
                
                valid_goals = [goal for goal in goal_objs_data.data if goal is not None]
                for goal_obj in valid_goals:
                    goal_dict=goal_obj
                    overall_gain_goals = 0
                    goal_id=goal_obj.get('goal_id')
                    okr_instances = okr.objects.filter(goal_id=goal_id, is_deleted=False).prefetch_related( "owners")
                    okr_list=[]
                    if okr_instances:
                        okr_serializer = okrserializers(okr_instances, many=True)
                        okr_serializers_data = okr_serializer.data
                        for okr_data in okr_serializers_data:
                            okr_dict= okr_data
                            all_key_results=okr_data.get('children')
                            overall_gain_avg = sum(d['overall_gain'] for d in all_key_results) / len(all_key_results) if all_key_results else 0
                            if overall_gain_avg is None:
                                overall_gain_avg = 0
                            else:
                                overall_gain_avg = round (overall_gain_avg)
                                overall_gain_goals += overall_gain_avg
                            okr_dict['overall_gain']=overall_gain_avg
                            okr_list.append(okr_dict)

                    goal_dict['children']=okr_list
                    try:
                        n = len(okr_instances)
                        overall_gain_goals_avg = round (overall_gain_goals / n)
                    except Exception:
                        overall_gain_goals_avg = 0
                    goal_dict['overall_gain'] = overall_gain_goals_avg

                    # Applying progress filter here
                    if progress_equal_to is not None:
                        if overall_gain_goals_avg != progress_equal_to:
                            continue

                    if progress_not_equal_to is not None:
                        if overall_gain_goals_avg == progress_not_equal_to:
                            continue

                    if last_updated_never:
                        if overall_gain_goals_avg != 0:
                            continue

                    if progress_less_than is not None:
                        if overall_gain_goals_avg >= progress_less_than:
                            continue    

                    if progress_greater_than is not None:   
                        if overall_gain_goals_avg < progress_greater_than:
                            continue

                    all_goals.append(goal_dict)
                    
            return Response(all_goals)
        except Goal.DoesNotExist:
            return Response({'error': 'Goal not found'}, status=status.HTTP_404_NOT_FOUND)
        except company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

    def put(self,request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Update"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
 
        goal_id = request.data.get('goal_id')
        user_ids=request.data.get('user_id')
        team_ids=request.data.get('team_id')
        delete_parent = request.data.get('deleted_parent',False)
        p_id = request.data.get('parent','') # p_id can be goal id, okr id, key_result id
        parent_type = request.data.get('parent_type','')  # parent_type can be goal , okr , key_result 
        description = request.data.get('description', None)
        title = request.data.get('title', None)

        try:
            target = Goal.objects.get(goal_id=goal_id)
        except Goal.DoesNotExist:
            return Response({"detail": "goal not found."}, status=status.HTTP_404_NOT_FOUND)

        if p_id and parent_type:
            # here I am updating either old parent with new one or assign new parent first time
            parent_id = update_parents(p_id,parent_type,target)
        elif delete_parent:
            # here deleting the parent from goal (set parent field empty ) and Parents table
            try:
                parent = Parents.objects.get(parent_id=target.parent_id).delete()
            except Parents.DoesNotExist:
                return Response({"detail": "Parents not found."}, status=status.HTTP_404_NOT_FOUND)
            parent_id = None
        else:
            parent_id= target.parent_id

        data = request.data
        data['parent_id']=parent_id    
        serializer = GoalSerializers(target, data=data, partial=True)
        changes = {'userOwners': {'oldValue': [], 'newValue': []}, 'teamOwners': {'oldValue': [], 'newValue': []}, 
                   'description': {'oldValue': None, 'newValue': None},'title': {'oldValue': None, 'newValue': None}}
        goal_id=Goal.objects.get(goal_id=goal_id)
        if user_ids is not None:
            old_user_owner = goal_owners.objects.filter(goal_id=goal_id,user_id__isnull=False)
            changes['userOwners']['oldValue'] = [{'username' : owner.user_id.username , 'profile_image' : owner.user_id.profile_image ,"type" : "user"} for owner in old_user_owner]
            old_user_owner.delete()
            changes['userOwners']['newValue'] = []
            for user_id in user_ids:
                try:
                    user_id = User.objects.get(user_id=user_id)
                    goal_owner_id = str(uuid.uuid4())
                    Owners = goal_owners(
                        user_id=user_id,
                        goal_owner_id=goal_owner_id,
                        goal_id=goal_id
                    )
                    Owners.save()
                    changes['userOwners']['newValue'].append({'username': user_id.username, 'profile_image': user_id.profile_image, "type": "user"})
                except User.DoesNotExist:
                    return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)
        if team_ids is not None:
            old_team_user = goal_owners.objects.filter(goal_id=goal_id,team_id__isnull=False)
            changes['teamOwners']['oldValue'] = [{'team_name' : owner.team_id.team_name ,"type" : "team"} for owner in old_team_user]
            old_team_user.delete() 
            changes['teamOwners']['newValue'] = []
            for team_id in team_ids:
                try:
                    team = team_Table.objects.get(team_id=team_id)
                    goal_owner_id = str(uuid.uuid4())
                    Owners = goal_owners(
                        team_id=team,
                        goal_owner_id=goal_owner_id,
                        goal_id=goal_id
                    )
                    Owners.save()
                    changes['teamOwners']['newValue'].append({'team_name' : team.team_name ,"type" : "team"})
                except User.DoesNotExist:
                    return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)
        if description:
            old_description = target.description
            changes['description']['oldValue'] = old_description
            changes['description']['newValue'] = description  

        if title:
            old_title = target.title
            changes['title']['oldValue'] = old_title
            changes['title']['newValue'] = title

        if serializer.is_valid():
            serializer.save() 
            if login_user_id:
                user = User.objects.get(user_id=login_user_id)
                company_id = target.company_id.company_id
                message = user.username + " edited the goal "
                changes['goal_id'] = str(goal_id.goal_id)
                employee_user_ids = []
                if team_ids:
                    for team_id in team_ids:
                        employee_ids = team_employees.objects.filter(team_id=team_id).values_list('user_id_id', flat=True)
                        employee_user_ids.extend(employee_ids)
                else:
                    team_ids= []
                save_notification(company_id, message, user, "goal", target.title,changes)

            if target.trello_board_id:
                try:
                    api_key, token = get_trello_credentials(login_user_id)
                    if api_key and token:
                        update_trello_board(api_key, token, target.trello_board_id, title)
                    else:
                        logger.warning(f"Trello credentials not found for user {login_user_id}.")
                except Exception as e:
                    logger.error(f"Error while updating Trello board: {e}")

            if target.asana_project_id:  
                try:
                    user_asana_token = AsanaConnection.objects.get(user_id=login_user_id) 
                    update_asana_project(user_asana_token, title, target.asana_project_id)
                except AsanaConnection.DoesNotExist:
                    return Response({"error": "Asana token not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self,request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Delete"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        goal_id=request.query_params.get('goal_id')   
        try:
            goal_obj = Goal.objects.get(goal_id=goal_id)
            # try:
            #     asana_connection = AsanaConnection.objects.get(user=login_user_id)
            # except AsanaConnection.DoesNotExist:
            #     asana_connection = None
            # if goal_obj.asana_project_id:
            #     delete_asana_project(asana_connection, goal_obj.asana_project_id)
            # # may be that goal define somewhere parent
            # if goal_obj.trello_board_id:
            #     api_key, token = get_trello_credentials(login_user_id)
            #     if api_key and token:
            #         trello_deleted = delete_trello_board(api_key, token, goal_obj.trello_board_id)
            #         if trello_deleted:
            #             logger.info(f"Trello board {goal_obj.trello_board_id} deleted successfully.")
            #         else:
            #             logger.warning(f"Failed to delete Trello board {goal_obj.trello_board_id}.")
        
            goal_obj = Goal.objects.get(goal_id=goal_id, is_deleted=False)  
            goal_obj.is_deleted = True  
            goal_obj.save()  
            changes = {'userOwners': {'oldValue': [], 'newValue': []}, 'description': {'oldValue': None, 'newValue': None},'title': {'oldValue': None, 'newValue': None}}
            if login_user_id:
                user = User.objects.get(user_id=login_user_id)
                message = f"{user.username} moved the goal to trash"
                old_value = {'username': user.username, 'profile_image': user.profile_image, 'type': 'user'}
                changes['userOwners']['oldValue'].append(old_value)
                save_notification(company_id, message, user, "goal", title=goal_obj.title, changes=changes, isDeleted=True)

            return Response({'message': 'Goal moved to trash successfully'}, status=status.HTTP_202_ACCEPTED)
        except Goal.DoesNotExist:
            return Response({'error': 'Goal not found'}, status=status.HTTP_404_NOT_FOUND)


class okr_details(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Create"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        goal_id=request.data.get('goal_id')
        okr_id=str(uuid.uuid4())
        session=request.data.get('session','')
        title=request.data.get('title','')
        user_ids = request.data.get('user_id',[])
        team_ids = request.data.get('team_id',[])
        description=request.data.get('description','')
        p_id = request.data.get('parent','') # p_id can be goal id only
        parent_type = request.data.get('parent_type','')  # parent_type can be goal only
        try:    
            goal_obj=Goal.objects.get(goal_id=goal_id)
        except Goal.DoesNotExist:
            return Response({'error': 'Goal not found'}, status=status.HTTP_404_NOT_FOUND)

        if p_id and parent_type:
            parent_id= save_parents(p_id,parent_type,'okr')
        else:
            parent_id =None
        
        Okr=okr(
            okr_id=okr_id,
            session=session,
            goal_id=goal_obj,
            title=title,
            parent_id=parent_id,
            description=description
        )
        Okr.save()

        # updating overall gain in okr and goal 
        filtered_okr = okr.objects.filter(goal_id = goal_id)
        goal_obj.average_gain = get_goal_progress(filtered_okr) 
        goal_obj.save()
   
        okr_obj =okr.objects.get(okr_id=okr_id)
        for user_id in user_ids:
            try:
                user_id = User.objects.get(user_id=user_id)
                owners_id = str(uuid.uuid4())
                Owners = owners(
                    user_id=user_id,
                    okr_id=okr_obj,
                    owners_id=owners_id,
                )
                Owners.save()
            except User.DoesNotExist:
                return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)
            
        # for assign goal owner to team
        for team_id in team_ids:
            try:
                team=team_Table.objects.get(team_id=team_id)
                Owners=owners(
                    owners_id=str(uuid.uuid4()),
                    team_id=team,
                    okr_id=okr_obj,
                )
                Owners.save()
            except team_Table.DoesNotExist:
                return Response({'error':'Team not found'},status=status.HTTP_404_NOT_FOUND)

        serilizers=okrserializers(Okr)
        company_id = goal_obj.company_id.company_id
        if login_user_id:
            user = User.objects.get(user_id=login_user_id)
            message = user.username + " created the objectives "
            changes = {}
            changes['okr_id'] = str(okr_id)
            #Fetch the Goal(s) associated with the given okr_id
            goals = Goal.objects.filter(goal_id__in=okr.objects.filter(okr_id=okr_id).values_list('goal_id', flat=True))
            #Fetch user_ids from goal_owners where goal_id matches
            user_ids = goal_owners.objects.filter(goal_id__in=goals).values_list('user_id', flat=True)
            save_notification(company_id, message, user, "objective", title=Okr.title, changes=changes)
        
        # creating story on jira 
        epic_key = goal_obj.epic_key 
        if epic_key and validate_jira(company_id):
            story_key = create_story(epic_key, title, description, company_id) 
            if story_key:
                okr_obj.story_key = story_key
                okr_obj.save()

        api_key, token = get_trello_credentials(user_id)
        if goal_obj.trello_board_id and validate_trello(api_key, token):
            list_id = trello_get_or_create_list(user_id, goal_obj.trello_board_id, "To Do")
            if list_id:
                card_id = trello_create_card(user_id, list_id, name=okr_obj.title, description=okr_obj.description)
                if card_id:
                    okr_obj.trello_card_id = card_id
                    okr_obj.save()

        try:
            asana_connection = AsanaConnection.objects.get(user=user_id)
        except (AsanaConnection.DoesNotExist):
            asana_connection = None
        if goal_obj.asana_project_id and asana_connection:
            try:
                asana_access_token = asana_connection.access_token
                sections_response = get_project_sections(goal_obj.asana_project_id, asana_access_token)

                if sections_response:
                    sections = sections_response.get("data", [])
                    to_do_section_id = next((section["gid"] for section in sections if section["name"].lower() == "to do"), None)

                    if to_do_section_id:
                        task_id = create_asana_task(
                            asana_access_token,
                            goal_obj.asana_project_id,
                            to_do_section_id,  
                            title,
                            description
                        )
                        if task_id:
                            okr_obj.asana_task_id = task_id
                            okr_obj.save()
                else:
                    logger.error(f"Failed to fetch sections for project {goal_obj.asana_project_id}: {sections_response}")
            except Exception as e:
                logger.error(f"Error creating Asana task for goal {goal_obj}: {e}")

        
        return Response(serilizers.data,status=status.HTTP_201_CREATED)
    
    def get(self,request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "View"
        role_id= validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        okr_id=request.query_params.get('okr_id')
        try:
            okrs=okr.objects.get(okr_id=okr_id)
        except okr.DoesNotExist:
            return Response({'error': 'OKR not found'}, status=status.HTTP_404_NOT_FOUND)
        data={}
        serializer=okrserializers(okrs)
        goal_id=serializer.data.get('goal_id')
        goal_obj=Goal.objects.get(goal_id=goal_id)
        goal_serializer=GoalSerializers(goal_obj)
        data=goal_serializer.data
        childern_list=[]
        children_dict={}
        children_dict=serializer.data
        childern_list.append(children_dict)
        data['children']=childern_list
        return Response(data)
        
    def put(self,request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Update"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
 
        okr_id = request.data.get('okr_id')
        team_ids = request.data.get('team_id')
        p_id = request.data.get('parent','') # p_id can be goal id only
        parent_type = request.data.get('parent_type','') #parent_type can be goal only
        child_type = request.data.get('child_type')
        description = request.data.get('description', None)
        title = request.data.get('title', None)
        try:
            target = okr.objects.get(okr_id=okr_id)
        except okr.DoesNotExist:
            return Response({"detail": "okr not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if p_id and parent_type:
            parent_id = save_parents(p_id,parent_type,child_type)
        else:
            parent_id=None
        
        data = request.data
        data['parent_id']=parent_id

        serializer = okrserializers(target, data=data, partial=True)
        changes = {'userOwners': {'oldValue': [], 'newValue': []}, 'teamOwners': {'oldValue': [], 'newValue': []}, 
                   'description': {'oldValue': None, 'newValue': None}, 'title': {'oldValue': None, 'newValue': None}}
        user_ids=request.data.get('user_id')
        okr_id=okr.objects.get(okr_id=okr_id)
        if user_ids is not None:
            old_user_owner = owners.objects.filter(okr_id=okr_id, user_id__isnull=False)
            changes['userOwners']['oldValue'] = [{'username': owner.user_id.username, 'profile_image': owner.user_id.profile_image, "type": "user"} for owner in old_user_owner]
            old_user_owner.delete()
            changes['userOwners']['newValue'] = []
            # owners.objects.filter(okr_id=okr_id,user_id__isnull=False).delete()
            for user_id in user_ids:
                try:
                    user_id = User.objects.get(user_id=user_id)
                    owners_id = str(uuid.uuid4())
                    Owners = owners(
                        user_id=user_id,
                        okr_id=okr_id,
                        owners_id=owners_id,
                    )
                    Owners.save()
                    changes['userOwners']['newValue'].append({'username': user_id.username, 'profile_image': user_id.profile_image, "type": "user"})
                except User.DoesNotExist:
                    return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)
        if team_ids is not None:
            old_team_user = owners.objects.filter(okr_id=okr_id, team_id__isnull=False)
            changes['teamOwners']['oldValue'] = [{'team_name': owner.team_id.team_name, "type": "team"} for owner in old_team_user]
            old_team_user.delete()
            changes['teamOwners']['newValue'] = []
            for team_id in team_ids:
                try:
                    team = team_Table.objects.get(team_id=team_id)
                    owners_id = str(uuid.uuid4())
                    Owners = owners(
                        team_id=team,
                        okr_id=okr_id,
                        owners_id=owners_id,
                    )
                    Owners.save()
                    changes['teamOwners']['newValue'].append({'team_name': team.team_name, "type": "team"})
                except User.DoesNotExist:
                    return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)  
        if description:
            old_description = target.description
            changes['description']['oldValue'] = old_description
            changes['description']['newValue'] = description 
        
        if title:
            old_title = target.title
            changes['title']['oldValue'] = old_title
            changes['title']['newValue'] = title       
        if serializer.is_valid():
            serializer.save() 

            if target.asana_task_id:
                asana_connection = AsanaConnection.objects.get(user_id=login_user_id)
                update_data = {
                    'name': title,  
                    'notes': description, 
                }
                update_asana_task(asana_connection, target.asana_task_id, update_data)
            
            if target.trello_card_id:
                api_key, token = get_trello_credentials(login_user_id)
                if api_key and token:
                    update_trello_card(
                        api_key=api_key,
                        token=token,
                        card_id=target.trello_card_id,
                        new_title=title,
                        new_description=description
                    )

            if login_user_id:
                user = User.objects.get(user_id=login_user_id)
                company_id = target.goal_id.company_id.company_id
                message = user.username + " edited the objectives " 
                changes['okr_id'] = str(okr_id.okr_id)
                #Fetch the Goal(s) associated with the given okr_id
                goals = Goal.objects.filter(goal_id__in=okr.objects.filter(okr_id=okr_id).values_list('goal_id', flat=True))
                #Fetch user_ids from goal_owners where goal_id matches
                user_ids = goal_owners.objects.filter(goal_id__in=goals).values_list('user_id', flat=True)
                save_notification(company_id, message, user, "objective", title=target.title, changes=changes)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    def delete(self,request):
        okr_id=request.query_params.get('okr_id')
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Delete"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
 
        try:
            okr_obj = okr.objects.get(okr_id=okr_id, is_deleted=False)
            okr_obj.is_deleted = True
            okr_obj.save()

            goal_obj = okr_obj.goal_id
            # if okr_obj.asana_task_id:
            #     asana_connection = AsanaConnection.objects.get(user_id=login_user_id)
            #     delete_asana_task(asana_connection, okr_obj.asana_task_id)
            
            # if okr_obj.trello_card_id:
            #     api_key, token = get_trello_credentials(login_user_id)
            #     if api_key and token:
            #         trello_deleted = delete_trello_card(api_key, token, okr_obj.trello_card_id)
            #         if trello_deleted:
            #             logger.info(f"Trello card {okr_obj.trello_card_id} deleted successfully.")
            #         else:
            #             logger.warning(f"Failed to delete Trello card {okr_obj.trello_card_id}.")

            filtered_okr = okr.objects.filter(goal_id = goal_obj.goal_id, is_deleted=False)
            goal_obj.average_gain = get_goal_progress(filtered_okr) 
            goal_obj.save()
            changes = {'userOwners': {'oldValue': [], 'newValue': []},  'description': {'oldValue': None, 'newValue': None},'title': {'oldValue': None, 'newValue': None}}
            if login_user_id:
                user = User.objects.get(user_id=login_user_id)
                company_id = goal_obj.company_id.company_id
                message = user.username + " deleted the objectives "
                old_value = {'username': user.username, 'profile_image': user.profile_image, 'type': 'user'}
                changes['userOwners']['oldValue'].append(old_value)
                #Fetch the Goal(s) associated with the given okr_id
                goals = Goal.objects.filter(goal_id__in=okr.objects.filter(okr_id=okr_id).values_list('goal_id', flat=True))
                #Fetch user_ids from goal_owners where goal_id matches
                user_ids = goal_owners.objects.filter(goal_id__in=goals).values_list('user_id', flat=True)
                save_notification(company_id, message, user, "objective", title=okr_obj.title , changes=changes, isDeleted=True)
                changes['userOwners']['newValue'] = None
            return Response({'message': 'OKR deleted successfully'}, status=status.HTTP_202_ACCEPTED)
        except okr.DoesNotExist:
            return Response({'error': 'OKR not found'}, status=status.HTTP_404_NOT_FOUND)

class key_result(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Create"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        okr_id=request.data.get('okr_id')
        key_id=str(uuid.uuid4())
        title=request.data.get('title','')
        key_result_type=request.data.get('key_result_type','')
        unit=request.data.get('unit','')
        target_number=request.data.get('target_number','')
        initial_number=request.data.get('initial_number','')
        current_number=initial_number
        description=request.data.get('description','')
        deadline_str = request.data.get('deadline','')
        team_ids = request.data.get('team_id',[])
        if not deadline_str: 
            deadline = None  
        else:
            try:
                deadline = date_parser.parse(deadline_str)
            except ValueError:
                deadline = None
        user_ids = request.data.get('user_id',[])
        try:
            Okr = okr.objects.get(okr_id=okr_id)
        except okr.DoesNotExist:
            return Response({"error": "okr not found"}, status=status.HTTP_404_NOT_FOUND)
        key_result_instance = key_results(
            okr_id=Okr,
            key_id=key_id,
            title=title,
            key_result_type=key_result_type,
            unit=unit,
            target_number=target_number,
            initial_number=initial_number,
            current_number=current_number,
            description=description,
            deadline=deadline,
        )
        key_result_instance.save()
        key_obj = key_results.objects.get(key_id=key_id)

        # updating overall gain in okr and goal
        okr_obj = key_obj.okr_id
        okr_obj.average_gain = get_okr_progress(okr_obj.okr_id)
        okr_obj.save()
        goal_obj = okr_obj.goal_id
        filtered_okr = okr.objects.filter(goal_id = goal_obj.goal_id)
        goal_obj.average_gain = get_goal_progress(filtered_okr) 
        goal_obj.save()

        for user_id in user_ids:
            try:
                user_id = User.objects.get(user_id=user_id)
                result_owners_id = str(uuid.uuid4())
                Result_Owner = result_owner(
                    user_id=user_id,
                    key_id=key_obj,
                    result_owner_id=result_owners_id,
                )
                Result_Owner.save()
            except User.DoesNotExist:
                return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)

        # for assign goal owner to team
        for team_id in team_ids:
            try:
                team=team_Table.objects.get(team_id=team_id)
                Owners=result_owner(
                    result_owner_id=str(uuid.uuid4()),
                    team_id=team,
                    key_id=key_obj,
                )
                Owners.save()  
            except team_Table.DoesNotExist:
                return Response({'error':'Team not found'},status=status.HTTP_404_NOT_FOUND)   

        company_id = goal_obj.company_id.company_id
        if login_user_id:
            user = User.objects.get(user_id=login_user_id)
            message = user.username + " created the key result "
            changes = {}
            changes['key_id'] = str(key_id)
            # Fetch the okr instance related to the given key_id
            okr_instance = key_results.objects.filter(key_id=key_id).values_list('okr_id', flat=True).first()
            
            if not okr_instance:
                return None  
            # Fetch the goal instance related to the fetched okr_id
            goal_instance = okr.objects.filter(okr_id=okr_instance).values_list('goal_id', flat=True).first()
            
            if not goal_instance:
                return None 
            # Fetch the user_ids from goal_owners related to the fetched goal_id
            user_ids = goal_owners.objects.filter(goal_id=goal_instance).values_list('user_id', flat=True)
        
            save_notification(company_id, message, user, "key result", title=key_obj.title, changes=changes)     

        # creating subtask over JIRA
        story_key = Okr.story_key
        if story_key and validate_jira(company_id):
            subtask_key = create_subtask(story_key, title, description , company_id)
            if subtask_key:
                key_obj.subtask_key = subtask_key
                key_obj.save()
        user_id = User.objects.get(user_id=login_user_id)
        api_key, token = get_trello_credentials(user_id)
        if okr_obj.trello_card_id and validate_trello(api_key, token):
            checklist_id = okr_obj.trello_checklist_id

            if not checklist_id:
                checklist_id = trello_create_checklist(user_id, okr_obj.trello_card_id, "Key Results")
                
                if checklist_id:
                    okr_obj.trello_checklist_id = checklist_id
                    okr_obj.save()

            if checklist_id:
                item_id = trello_add_checklist_item(user_id, checklist_id, key_result_instance.title)                
                if item_id:
                    key_result_instance.trello_checklist_item_id = item_id
                    key_result_instance.save()

        try:
            asana_connection = AsanaConnection.objects.get(user=user_id)
        except (AsanaConnection.DoesNotExist):
            asana_connection = None

        if okr_obj.asana_task_id and asana_connection:
            subtask_id = create_asana_subtask(
                asana_connection.access_token, okr_obj.asana_task_id, title, description)
            
            if subtask_id:
                key_result_instance.asana_subtask_id = subtask_id
                key_result_instance.save()
            else:
                return Response({"detail": "Failed to create Asana subtask."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({"detail": "Asana task ID for OKR not found."}, status=status.HTTP_400_BAD_REQUEST)
       
        serilizers=key_resultsserializers(key_result_instance)
        return Response(serilizers.data,status=status.HTTP_201_CREATED)

    def get(self,request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "View"
        role_id= validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        key_id=request.query_params.get('key_id')

        try:
            if key_id:
                key_data=key_results.objects.get(key_id=key_id)
                serilizer=key_resultsserializers(key_data)
                data=serilizer.data
                return Response(data, status=status.HTTP_200_OK)
 
            else:
                upcoming_or_missed_deadline = []
                company_obj = company.objects.get(company_id=company_id)

                current_date = datetime.now().date()
                start_date = current_date - timedelta(days=15)
                end_date = current_date + timedelta(days=15)
                
                key_results_instance = key_results.objects.filter(
                    okr_id__goal_id__company_id=company_id,
                    deadline__range=(start_date, end_date)
                )

                # Serialize the necessary fields
                key_result_data = key_resultsserializers(key_results_instance, many=True).data

                # Use a dictionary to group key results by deadline
                key_results_by_deadline = {}
                for item in key_result_data:
                    deadline = item['deadline']
                    if deadline not in key_results_by_deadline:
                        deadline = deadline.split("T")[0]
                        deadline_str = datetime.strptime(deadline, "%Y-%m-%d")
                        key_results_by_deadline[str(deadline_str.date())] = []
                    key_results_by_deadline[str(deadline_str.date())].append(item)

                
                # Pre-generate all necessary date strings
                date_strings = {start_date + timedelta(days=n): str(start_date + timedelta(days=n)) for n in range((end_date - start_date).days)}

                # Build the upcoming_or_missed_deadline list
                upcoming_or_missed_deadline = [
                    {
                        "deadline": date_str,
                        "key_results": key_results_by_deadline.get(date_str, [])
                    }
                    for date, date_str in date_strings.items()
                ]

                return Response({"upcoming_or_missed_deadline" : upcoming_or_missed_deadline}, status=status.HTTP_200_OK)

        except key_results.DoesNotExist:
            return Response({'error': 'key not found'}, status=status.HTTP_404_NOT_FOUND)

        except company.DoesNotExist:
            return Response( {"error": "company not found"}, status=status.HTTP_404_NOT_FOUND )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        

    def put(self, request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Update"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)
 
        key_id = request.data.get('key_id')
        parent = request.data.get('parent' ,'')
        p_id = request.data.get('parent_id','') # p_id can be  okr id only
        parent_type = request.data.get('parent_type','') # parent_type can be  okr only
        target_number = request.data.get('target_number' ,'')
        initial_number = request.data.get('initial_number' ,'')
        description = request.data.get('description', None)
        title = request.data.get('title', None)
        try:
            target = key_results.objects.get(key_id=key_id)
        except key_results.DoesNotExist:
            return Response({"detail": "Key not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = key_resultsserializers(target, data=request.data, partial=True)
        changes = {'userOwners': {'oldValue': [], 'newValue': []}, 'teamOwners': {'oldValue': [], 'newValue': []}, 
                   'description': {'oldValue': None, 'newValue': None}, 'title': {'oldValue': None, 'newValue': None}}
        user_ids = request.data.get('user_id')
        team_ids = request.data.get('team_id')
        if user_ids is not None:
            old_user_owner = result_owner.objects.filter(key_id=key_id, user_id__isnull=False)
            changes['userOwners']['oldValue'] = [{'username': owner.user_id.username,
                                              'profile_image': owner.user_id.profile_image, "type": "user"} for owner
                                             in old_user_owner]
            old_user_owner.delete()
            changes['userOwners']['newValue'] = []
            for user_id in user_ids:
                try:
                    user_id = User.objects.get(user_id=user_id)
                    result_owner_id = str(uuid.uuid4())
                    Owners = result_owner(
                        user_id=user_id,
                        key_id=target,
                        result_owner_id=result_owner_id,
                    )
                    Owners.save()
                    changes['userOwners']['newValue'].append({'username': user_id.username, 'profile_image': user_id.profile_image, "type": "user"})
                except User.DoesNotExist:
                    return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)
        if team_ids is not None:
            old_team_user = result_owner.objects.filter(key_id=key_id, team_id__isnull=False)
            changes['teamOwners']['oldValue'] = [{'team_name': owner.team_id.team_name, "type": "team"} for owner in old_team_user]
            old_team_user.delete()
            changes['teamOwners']['newValue'] = []
            for team_id in team_ids:
                try:
                    team = team_Table.objects.get(team_id=team_id)
                    result_owner_id = str(uuid.uuid4())
                    Owners = result_owner(
                        team_id=team,
                        key_id=target,
                        result_owner_id=result_owner_id,
                    )
                    Owners.save()
                    changes['teamOwners']['newValue'].append({'team_name': team.team_name, "type": "team"})
                except User.DoesNotExist:
                    return Response({'error':'User not found'},status=status.HTTP_404_NOT_FOUND)

        if parent and p_id:
            # here I am updating either old parent with new one or assign new parent first time
            update_parents(p_id,parent_type,parent)
        if description:
            old_description = target.description
            changes['description']['oldValue'] = old_description
            changes['description']['newValue'] = description    

        if title:
            old_title = target.title
            changes['title']['oldValue'] = old_title
            changes['title']['newValue'] = title
        if serializer.is_valid():
            serializer.save()
            if target.asana_subtask_id:
                asana_connection = AsanaConnection.objects.get(user_id=login_user_id)
                update_data = {
                    'name': title,  
                    'notes': description, 
                }
                update_asana_task(asana_connection, target.asana_subtask_id, update_data) 

            if target.trello_checklist_item_id:
                api_key, token = get_trello_credentials(login_user_id)
                card_id =target.okr_id.trello_card_id 
                if api_key and token:
                    update_trello_checklist_item(api_key, token, card_id, target.trello_checklist_item_id, title)
                else:
                    logger.warning(f"Trello credentials not found for user {login_user_id}.")
            
            data = serializer.data
            if initial_number or target_number:
                overall_gain = update_base_calculation(key_id)
                data['overall_gain'] = overall_gain

            if login_user_id:
                user = User.objects.get(user_id=login_user_id)
                company_id = target.okr_id.goal_id.company_id.company_id
                message = user.username + " edited the key result "
                changes['key_id'] = str(key_id)
                # Fetch the okr instance related to the given key_id
                okr_instance = key_results.objects.filter(key_id=key_id).values_list('okr_id', flat=True).first()
                
                if not okr_instance:
                    return None  
                # Fetch the goal instance related to the fetched okr_id
                goal_instance = okr.objects.filter(okr_id=okr_instance).values_list('goal_id', flat=True).first()
                
                if not goal_instance:
                    return None 
                # Fetch the user_ids from goal_owners related to the fetched goal_id
                user_ids = goal_owners.objects.filter(goal_id=goal_instance).values_list('user_id', flat=True)
                save_notification(company_id, message, user, "key result", title= target.title, changes=changes)
            return Response(data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self,request):
        
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Delete"
        role_id= validate_user_company_access(login_user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        key_id=request.query_params.get('key_id')
        try:
            key_obj = key_results.objects.get(key_id=key_id)
            # may be that key_results define somewhere parent
            # if key_obj.asana_subtask_id:
            #     asana_connection = AsanaConnection.objects.get(user_id=login_user_id)
            #     delete_asana_task(asana_connection, key_obj.asana_subtask_id)

            # if key_obj.trello_checklist_item_id:
            #     api_key, token = get_trello_credentials(login_user_id)
            #     if api_key and token:
            #         card_id = key_obj.okr_id.trello_card_id 
            #         checklist_id = key_obj.okr_id.trello_checklist_id  
            #         delete_trello_checklist_item(api_key, token, card_id, checklist_id, key_obj.trello_checklist_item_id)
            #     else:
            #         logger.warning(f"Trello credentials not found for user {login_user_id}.")

            key_obj = key_results.objects.get(key_id=key_id, is_deleted=False)
            key_obj.is_deleted = True
            key_obj.save()

            # Recalculate OKR and Goal progress
            okr_obj = key_obj.okr_id
            okr_obj.average_gain = get_okr_progress(okr_obj.okr_id)
            okr_obj.save()

            goal_obj = okr_obj.goal_id
            filtered_okr = okr.objects.filter(goal_id=goal_obj.goal_id, is_deleted=False)
            goal_obj.average_gain = get_goal_progress(filtered_okr)
            goal_obj.save()
            changes = {'userOwners': {'oldValue': [], 'newValue': []}, 'description': {'oldValue': None, 'newValue': None},'title': {'oldValue': None, 'newValue': None}}
            if login_user_id:
                user = User.objects.get(user_id=login_user_id)
                company_id = goal_obj.company_id.company_id
                message = user.username + " deleted the key result "
                old_value = {'username': user.username, 'profile_image': user.profile_image, 'type': 'user'}
                changes['userOwners']['oldValue'].append(old_value)
                # Fetch the okr instance related to the given key_id
                okr_instance = key_results.objects.filter(key_id=key_id).values_list('okr_id', flat=True).first()
                
                if not okr_instance:
                    return None  
                # Fetch the goal instance related to the fetched okr_id
                goal_instance = okr.objects.filter(okr_id=okr_instance).values_list('goal_id', flat=True).first()
                
                if not goal_instance:
                    return None 
                # Fetch the user_ids from goal_owners related to the fetched goal_id
                user_ids = goal_owners.objects.filter(goal_id=goal_instance).values_list('user_id', flat=True)
                save_notification(company_id, message, user, "key result", title=key_obj.title, changes=changes, isDeleted=True)
                changes['userOwners']['newValue'] = None
            return Response({'message': 'key deleted successfully'}, status=status.HTTP_202_ACCEPTED)
        except key_results.DoesNotExist:
            return Response({'error': 'key not found'}, status=status.HTTP_404_NOT_FOUND)

class updatekeyresults(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        update_key_id=str(uuid.uuid4())
        key_id=request.data.get('key_id')
        new_number=request.data.get('new_number')
        confidenece_level=request.data.get('confidence_level')
        note=request.data.get('note','')
        changed_at = request.data.get('changed_at')
        company_id = request.data.get('company_id')
        login_user_id = GetUserId.get_user_id(request)
        try:
            key_obj=key_results.objects.get(key_id=key_id)
            company_obj=company.objects.get(company_id=company_id)
            user_obj=User.objects.get(user_id=login_user_id)
        except key_results.DoesNotExist:
            return Response({"error": "key not found"}, status=status.HTTP_404_NOT_FOUND)
        except company.DoesNotExist:
            return Response({"error": "company  not found"}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "user not found"}, status=status.HTTP_404_NOT_FOUND)
        okr_obj = key_obj.okr_id
        initial_number = key_obj.initial_number
        target_number  = key_obj.target_number
        if target_number == initial_number:
            gain = 0 
        else:
            gain=(new_number-initial_number)/(target_number-initial_number)*100
        update_keyresults_instance=update_key_results(
            update_key_id=update_key_id,
            key_id=key_obj,
            new_number=new_number,
            company_id=company_obj,
            user_id=user_obj,
            confidence_level=confidenece_level,
            note=note,
            gain=gain,
            changed_at=changed_at,
        )
        update_keyresults_instance.save()
        confidence_level_value = {'High': 3, 'Medium': 2 ,'Low' :1}
        key_obj.current_number=new_number
        key_obj.confidence_value = confidence_level_value.get(confidenece_level,1)
        key_obj.overall_gain = update_key_results.objects.filter(key_id=key_id).latest('changed_at').gain
        key_obj.save()
        okr_obj.average_gain = get_okr_progress(okr_obj)
        okr_obj.save()
        goal_obj = okr_obj.goal_id
        filtered_okr = okr.objects.filter(goal_id = goal_obj.goal_id)
        goal_obj.average_gain = get_goal_progress(filtered_okr) 
        goal_obj.save()
        serilizer=update_keyresultsserializers(update_keyresults_instance)
        if login_user_id:
            user = User.objects.get(user_id=login_user_id)
            company_id = goal_obj.company_id.company_id
            message = " key result updated by " +  user.username 
            changes = {}
            changes['key_id'] = str(key_id)
            # Fetch the okr instance related to the given key_id
            okr_instance = key_results.objects.filter(key_id=key_id).values_list('okr_id', flat=True).first()
                
            if not okr_instance:
                return None  
            # Fetch the goal instance related to the fetched okr_id
            goal_instance = okr.objects.filter(okr_id=okr_instance).values_list('goal_id', flat=True).first()
            
            if not goal_instance:
                return None 
            # Fetch the user_ids from goal_owners related to the fetched goal_id
            user_ids = goal_owners.objects.filter(goal_id=goal_instance).values_list('user_id', flat=True)
            save_notification(company_id, message, user, "key result", title=key_obj.title, changes=changes)
        return Response(serilizer.data,status=status.HTTP_200_OK)
    def get(self,request):
        key_id=request.query_params.get('key_id')
        try:
            key_obj=update_key_results.objects.filter(key_id=key_id).order_by('changed_at')
        except key_results.DoesNotExist:
            return Response({"error": "key not found"}, status=status.HTTP_404_NOT_FOUND)
        update_key=[]

        overall_gain=0
        gain=0
        previous_overall_gain = 0
        key_results_obj=key_results.objects.get(key_id=key_id)
        results_serilizer=key_resultsserializers(key_results_obj)
        target_number=results_serilizer.data.get('target_number')
        initial_number=results_serilizer.data.get('initial_number')
        if key_obj:
            
            for keys in key_obj:
                update_key_dict={}
                serilizer=update_keyresultsserializers(keys)
                user_id=serilizer.data.get('user_id')
                user=User.objects.get(user_id=user_id)
                new_number=serilizer.data.get('new_number')
                if target_number == initial_number:
                    overall_gain = 0 
                else:
                    overall_gain= round ((new_number-initial_number)/(target_number-initial_number)*100)
                update_key_dict=serilizer.data
                update_key_dict['username']=user.username
                update_key_dict['profile_image']=user.profile_image
                update_key_dict['overall_gain']=overall_gain

                if previous_overall_gain ==0:
                    gain = overall_gain
                else:
                    gain=overall_gain-previous_overall_gain
                previous_overall_gain=overall_gain
                update_key_dict['gain']=gain
                update_key.append(update_key_dict)
        update_key.reverse()
        return Response(update_key)
    
    def delete(self, request):
        update_key_id = request.query_params.get('update_key_id')
        login_user_id = GetUserId.get_user_id(request)
        key_results_obj = None
        try:
            key_obj = update_key_results.objects.get(update_key_id=update_key_id)
            serilizer=update_keyresultsserializers(key_obj)
            key_id = serilizer.data.get('key_id')
           
            current_timestamp = key_obj.changed_at
            key_results_obj = key_results.objects.get(key_id=key_id)
            
            key_obj.delete()
            
            update_key_obj = update_key_results.objects.filter(key_id=key_id).order_by('-changed_at').first()
            if update_key_obj:
                key_results_obj.current_number = update_key_obj.new_number
                key_results_obj.overall_gain = update_key_obj.gain
            else:
                key_results_obj.overall_gain = 0
            key_results_obj.save()
            # updating overall gain in okr and goal 
            okr_obj = key_results_obj.okr_id
            okr_obj.average_gain = get_okr_progress(okr_obj)
            okr_obj.save()
            goal_obj = okr_obj.goal_id
            filtered_okr = okr.objects.filter(goal_id = goal_obj.goal_id)
            goal_obj.average_gain = get_goal_progress(filtered_okr) 
            goal_obj.save()
            changes = {'userOwners': {'oldValue': [], 'newValue': []},  'description': {'oldValue': None, 'newValue': None},'title': {'oldValue': None, 'newValue': None}}
            if login_user_id:
                user = User.objects.get(user_id=login_user_id)
                company_id = key_results_obj.okr_id.goal_id.company_id.company_id
                message = "key result deleted by " + user.username
                old_value = {'username': user.username, 'profile_image': user.profile_image, 'type': 'user'}
                changes['userOwners']['oldValue'].append(old_value)
                # Fetch the okr instance related to the given key_id
                okr_instance = key_results.objects.filter(key_id=key_id).values_list('okr_id', flat=True).first()
                
                if not okr_instance:
                    return None  
                # Fetch the goal instance related to the fetched okr_id
                goal_instance = okr.objects.filter(okr_id=okr_instance).values_list('goal_id', flat=True).first()
                
                if not goal_instance:
                    return None 
                # Fetch the user_ids from goal_owners related to the fetched goal_id
                user_ids = goal_owners.objects.filter(goal_id=goal_instance).values_list('user_id', flat=True)
                save_notification(company_id, message, user, "key result", title=key_results_obj.title, changes=changes, isDeleted=True)
                changes['userOwners']['newValue'] = None
            return Response({'message': 'Update key deleted successfully'}, status=status.HTTP_202_ACCEPTED)
        except update_key_results.DoesNotExist:
            if key_results_obj:
                key_results_obj.current_number=key_results_obj.initial_number
                key_results_obj.save()
            return Response({'message': 'Update key deleted successfully'}, status=status.HTTP_202_ACCEPTED)
        except key_results.DoesNotExist:
            return Response({'error': 'Key result not found'}, status=status.HTTP_404_NOT_FOUND)

class OKRListView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        goal_id = request.query_params.get('goal_id')

        if not goal_id:
            return Response({"error": "Goal ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate goal existence
        try:
            goal = Goal.objects.get(goal_id=goal_id)
        except Goal.DoesNotExist:
            return Response({"error": "Goal not found."}, status=status.HTTP_404_NOT_FOUND)

        # Fetch OKRs related to the goal_id
        okrs = okr.objects.filter(goal_id=goal)

        # Serialize the OKRs along with their key results
        serializer = OKRSerializer(okrs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class QuarterAPiView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        current_year = datetime.now().year
        current_month = datetime.now().month
        current_quarter = (current_month - 1) // 3 + 1

        quarters = []

        for year in range(current_year, current_year + 2):
            for quarter in range(1, 5):
                if year == current_year and quarter < current_quarter:
                    continue
                quarters.append({
                    "label": f"{year} Q{quarter}",
                    "value":f"{year}_Q{quarter}"
                })
                
        return Response(quarters)


class DeletedItemsView(APIView):
    permission_classes = [IsValidUser]
    
    def get(self, request):
        try:
            company_id = request.query_params.get('company_id') 

            if not company_id:
                return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

            goals = Goal.objects.filter(company_id=company_id,is_deleted=True)
            okrs = okr.objects.filter(is_deleted=True).prefetch_related( "owners")  
            key_result = key_results.objects.filter(is_deleted=True)

            goals_list = []
            okrs_list = []
            key_results_list = []
            for goal in goals:
                goal_dict = GoalSerializers(goal).data
                goal_dict['children'] = []
                okr_instances = okrs.filter(goal_id=goal.goal_id) 
                
                if okr_instances.exists(): 
                    for ok in okr_instances:
                        okr_dict = OKRSerializer(ok).data
                        okr_dict['children'] = []
                        key_result_instances = key_result.filter(okr_id=ok.okr_id)
                        key_result_serializer = key_resultsserializers(key_result_instances, many=True)
                        okr_dict['children'] = key_result_serializer.data
                        goal_dict['children'].append(okr_dict)

                goals_list.append(goal_dict)  
            
            for okr_instance in okrs:
                okr_dict = OKRSerializer(okr_instance).data
                okr_dict['children'] = []
                key_result_instances = key_result.filter(okr_id=okr_instance.okr_id)
                key_result_serializer = key_resultsserializers(key_result_instances, many=True)
                okr_dict['children'] = key_result_serializer.data
                okrs_list.append(okr_dict)

            for key_result in key_result:
                key_result_data = key_resultsserializers(key_result).data
                key_results_list.append(key_result_data)

            response_data = {
                "goals": goals_list,
                "okrs": okrs_list,
                "key_results": key_results_list
            }

            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_BAD_REQUEST)


    def post(self, request):
        try:
            goal_id = request.data.get("goal_id")
            okr_id = request.data.get("okr_id")
            key_result_id = request.data.get("key_id")

            if goal_id:
                Goal.objects.filter(goal_id=goal_id, is_deleted=True).update(is_deleted=False)
            if okr_id:
                okr.objects.filter(okr_id=okr_id, is_deleted=True).update(is_deleted=False)
            if key_result_id:
                key_results.objects.filter(key_id=key_result_id, is_deleted=True).update(is_deleted=False)

            return Response({"message": "Items restored successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_BAD_REQUEST)