from rest_framework import status
from imongu_backend_app.models import Goal,goal_owners, okr,owners,key_results
from imongu_backend_app.Serializers import GoalSerializers, okrserializers,key_resultsserializers
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
import uuid
from imongu_backend_app.utils.helper import *
from imongu_backend_app.utils.clone import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from django.shortcuts import get_object_or_404
from integrations.utils.trello import *
from integrations.models import AsanaConnection
from integrations.utils.asana_utils import *

class cloneJobs(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        current_id = request.data.get('current_id')  #that id refers to selected level (goal , okr , key _result )
        target_id = request.data.get('target_id')   #that id refers to assign level (goal , okr , key _result )
        current_type = request.data.get('current_type')
        target_type = request.data.get('target_type')
        login_user_id = GetUserId.get_user_id(request)

        # clone goal to goal that mean just add parent 
        if current_type=='goal':
            try:
                # Get the goal with the specified goal_id
                original_goal = Goal.objects.get(goal_id=current_id)            
                # Create a new goal by copying the attributes of the original goal and goal owners
                title = original_goal.title + ' clone'
                cloned_goal_data = { 'goal_id' : str(uuid.uuid4()) ,'company_id' : original_goal.company_id , 'title' : title , 'description' : original_goal.description , 'session' : original_goal.session}
                new_goal = Goal.objects.create(**cloned_goal_data)
                serializer = GoalSerializers(new_goal)
                goal_owners_queryset = goal_owners.objects.filter(goal_id=original_goal)
                for owner_data in goal_owners_queryset:
                    owner = {
                        'goal_owner_id' : str(uuid.uuid4()),
                        'goal_id' : new_goal ,
                        'user_id' : owner_data.user_id ,
                        'team_id' : owner_data.team_id
                    }
                    goal_owners.objects.create(**owner)

                # Clone OKRs and OKR owners
                original_okrs = okr.objects.filter(goal_id=current_id)
                for original_okr in original_okrs:
                    # Clone OKR
                    new_okr = okr.objects.create(
                        okr_id=str(uuid.uuid4()),
                        goal_id=new_goal,
                        title=original_okr.title,
                        description=original_okr.description,
                        
                    )

                    # Clone OKR owners
                    okr_owners = owners.objects.filter(okr_id=original_okr.okr_id)
                    for okr_owner_obj in okr_owners:
                        owners.objects.create(
                            owners_id=str(uuid.uuid4()),
                            okr_id=new_okr,
                            user_id=okr_owner_obj.user_id,
                            team_id=okr_owner_obj.team_id
                        )

                    clone_key_result(original_okr.okr_id, new_okr)

                # Trello Integration
                if original_okrs.exists():
                    for original_okr in original_okrs:
                        setup_trello_for_goal(new_goal.goal_id, original_okr.okr_id, login_user_id, request)
                else:
                    setup_trello_for_goal(new_goal.goal_id, None, login_user_id, request)

                # Asana Integration
                try:
                    asana_connection = AsanaConnection.objects.get(user=login_user_id)
                except AsanaConnection.DoesNotExist:
                    asana_connection = None

                if asana_connection:
                    asana_access_token = asana_connection.access_token
                    if original_okrs.exists():
                        for original_okr in original_okrs:
                            integrate_asana_for_goal(asana_access_token, new_goal.goal_id, original_okr.okr_id)
                    else:
                        integrate_asana_for_goal(asana_access_token, new_goal.goal_id, None)
                    

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Goal.DoesNotExist:
                return Response({'error': 'Goal not found'}, status=status.HTTP_404_NOT_FOUND)

        # Clone OKR to goal
        if current_type == 'okr' and target_type == 'goal':
            try:
                original_okr = okr.objects.get(okr_id=current_id)
                goal_instance = Goal.objects.get(goal_id=target_id)

                # Clone OKR
                new_okr = okr.objects.create(
                    okr_id=str(uuid.uuid4()),
                    goal_id=goal_instance,
                    title=original_okr.title,
                    description=original_okr.description,
                    # Add other fields as needed
                )

                # Clone OKR owners
                okr_owners = owners.objects.filter(okr_id=original_okr.okr_id)
                for okr_owner_obj in okr_owners:
                    owners.objects.create(
                        owners_id=str(uuid.uuid4()),
                        okr_id=new_okr,
                        user_id=okr_owner_obj.user_id,
                        team_id=okr_owner_obj.team_id
                    )

                # Clone key results and key result owners
                clone_key_result(original_okr.okr_id, new_okr)
                api_key, token = get_trello_credentials(login_user_id)
                if goal_instance.trello_board_id and validate_trello(api_key, token):
                    list_id = trello_get_or_create_list(login_user_id, goal_instance.trello_board_id, "To Do")
                    if list_id:
                        card_id = trello_create_card(login_user_id, list_id, name=new_okr.title, description=new_okr.description)
                        if card_id:
                            new_okr.trello_card_id = card_id
                            new_okr.save()
                            checklist_id = trello_create_checklist(login_user_id, card_id, "Key Results")
                            if checklist_id:
                                new_okr.trello_checklist_id = checklist_id
                                new_okr.save()
                                key_results_queryset = key_results.objects.filter(okr_id=new_okr.okr_id)
                                for kr in key_results_queryset:
                                    item_id = trello_add_checklist_item(
                                        login_user_id, checklist_id, kr.title
                                    )
                                    if item_id:
                                        kr.trello_checklist_item_id = item_id
                                        kr.save()

                try:
                    asana_connection = AsanaConnection.objects.get(user=login_user_id)
                except (AsanaConnection.DoesNotExist):
                    asana_connection = None

                if goal_instance.asana_project_id and asana_connection:
                    try:
                        asana_access_token = asana_connection.access_token
                        integrate_asana_for_okr(asana_access_token, goal_instance.goal_id)
                    except Exception as e:
                        logger.error(f"Error creating Asana task for goal {goal_instance}: {e}")
                return Response({'success': 'OKR cloned successfully'}, status=status.HTTP_201_CREATED)

            except okr.DoesNotExist:
                return Response({'error': 'OKR not found'}, status=status.HTTP_404_NOT_FOUND)

        # Clone key result to OKR
        if current_type == 'key_result' and target_type == 'okr':
            try:
                original_key_result = key_results.objects.get(key_id=current_id)
                okr_instance = okr.objects.get(okr_id=target_id)

                # Clone key result
                new_key_result = key_results.objects.create(
                    key_id=str(uuid.uuid4()),
                    okr_id=okr_instance,
                    title=original_key_result.title,
                    description=original_key_result.description,
                    target_number=original_key_result.target_number,
                    initial_number=original_key_result.initial_number,
                    current_number=original_key_result.current_number,
                    deadline=original_key_result.deadline,  
                    confidence_value=original_key_result.confidence_value,
                    subtask_key=original_key_result.subtask_key,
                    unit=original_key_result.unit,
                    trello_checklist_item_id=original_key_result.trello_checklist_item_id
                    # Add other fields if necessary
                )

                # Clone additional details if needed
                clone_updatekey(original_key_result.key_id, new_key_result)
                api_key, token = get_trello_credentials(login_user_id)
                if okr_instance.trello_card_id and validate_trello(api_key, token):
                    checklist_id = okr_instance.trello_checklist_id

                    if not checklist_id:
                        checklist_id = trello_create_checklist(login_user_id, okr_instance.trello_card_id, "Key Results")
                        
                        if checklist_id:
                            okr_instance.trello_checklist_id = checklist_id
                            okr_instance.save()

                    if checklist_id:
                        item_id = trello_add_checklist_item(login_user_id, checklist_id, new_key_result.title)                
                        if item_id:
                            new_key_result.trello_checklist_item_id = item_id
                            new_key_result.save()

                try:
                    asana_connection = AsanaConnection.objects.get(user=login_user_id)
                except (AsanaConnection.DoesNotExist):
                    asana_connection = None

                if okr_instance.asana_task_id and asana_connection:
                    subtask_id = create_asana_subtask(
                        asana_connection.access_token, okr_instance.asana_task_id, title, new_key_result.description) 
                    if subtask_id:
                        new_key_result.asana_subtask_id = subtask_id
                        new_key_result.save()
                    else:
                        return Response({"detail": "Failed to create Asana subtask."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                else:
                    return Response({"detail": "Asana task ID for OKR not found."}, status=status.HTTP_400_BAD_REQUEST)            
                return Response({'success': 'Key result cloned successfully'}, status=status.HTTP_201_CREATED)

            except key_results.DoesNotExist:
                return Response({'error': 'Key result not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'error': 'Invalid operation'}, status=status.HTTP_400_BAD_REQUEST)


class moveJobs(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        current_id = request.data.get('current_id')  #that id refers to selected level (goal , okr , key _result )
        target_id = request.data.get('target_id')   #that id refers to assign level (goal , okr , key _result )
        current_type = request.data.get('current_type')
        target_type = request.data.get('target_type')
        # move okr into goal
        if current_type=='okr' and target_type=='goal':
            goal_id = target_id
            okr_id = current_id
            objective = okr.objects.get(okr_id = okr_id)
            objective.goal_id = Goal.objects.get(goal_id=goal_id)
            objective.save()
        
        # move key_result into okr
        elif current_type=='key_result' and target_type=='okr':
            okr_id = target_id
            key_id = current_id
            keyresult = key_results.objects.get(key_id = key_id)
            keyresult.okr_id = okr.objects.get(okr_id=okr_id)
            keyresult.save()

        elif current_type == 'goal' and target_type == 'goal':
            parent_id = save_parents(target_id,target_type,"goal")
            goal_instance = Goal.objects.get(goal_id=current_id)
            goal_instance.parent_id = parent_id
            goal_instance.save()
        
        return Response( {"meesage" : "Moved successfully" }, status=status.HTTP_201_CREATED)
