from imongu_backend_app.models import key_results,result_owner,update_key_results, Goal, okr
from imongu_backend_app.Serializers import update_keyresultsserializers,key_resultsserializers
import uuid
from integrations.utils.trello import *
from integrations.utils.asana_utils import *
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

def clone_updatekey(key_id,new_key_id):
    key_owners = result_owner.objects.filter(key_id=key_id)
    for key_owner_obj in key_owners:
        key_owner = {
            'result_owner_id' : str(uuid.uuid4()),
            'key_id' : new_key_id ,
            'user_id' : key_owner_obj.user_id ,
            'team_id' : key_owner_obj.team_id
        }
        result_owner.objects.create(**key_owner)

    # clone update_key_results
    original_update_key = update_key_results.objects.filter(key_id=key_id)
    update_key_serializer = update_keyresultsserializers(original_update_key,many=True)
    for update_key , update_key_obj in zip(update_key_serializer.data ,original_update_key):
        update_key['update_key_id'] = str(uuid.uuid4())
        update_key['key_id'] = new_key_id
        update_key['company_id'] = update_key_obj.company_id
        update_key['user_id'] = update_key_obj.user_id
        new_update_keyresult = update_key_results.objects.create(**update_key)

def clone_key_result(okr_id, new_okr_id):
    original_keys = key_results.objects.filter(okr_id=okr_id)
    key_serializer = key_resultsserializers(original_keys, many=True)
    for key_data in key_serializer.data:
        key_id = key_data.get('key_id')

        # Remove unexpected fields like 'owners' from key_data
        if 'owners' in key_data:
            del key_data['owners']

        key_data['key_id'] = str(uuid.uuid4())
        key_data['okr_id'] = new_okr_id

        # Create the new key result with valid fields
        new_keyresult = key_results.objects.create(**key_data)
        clone_updatekey(key_id, new_keyresult)

def setup_trello_for_goal(goal_id, okr_id, login_user_id, request):
    try:
        api_key, token = get_trello_credentials(login_user_id)
        new_goal = Goal.objects.get(goal_id=goal_id)
        if api_key and token:
            board_id = trello_create_board(login_user_id, new_goal.title)
            if board_id:
                new_goal.trello_board_id = board_id
                new_goal.save()
                setup_webhooks(api_key, token, request)
                list_id = trello_get_or_create_list(login_user_id, board_id, "To Do")
                if list_id:
                    original_okrs = okr.objects.filter(goal_id=goal_id)
                    if original_okrs.exists():  
                        for new_okr in original_okrs:
                            card_id = trello_create_card(login_user_id, list_id, new_okr.title, new_okr.description)
                            if card_id:
                                new_okr.trello_card_id = card_id
                                new_okr.save()
                                checklist_id = trello_create_checklist(login_user_id, card_id, "Key Results")
                                if checklist_id:
                                    key_results_queryset = key_results.objects.filter(okr_id=new_okr.okr_id)
                                    for kr in key_results_queryset:
                                        item_id = trello_add_checklist_item(login_user_id, checklist_id, kr.title)
                                        if item_id:
                                            kr.trello_checklist_item_id = item_id
                                            kr.save()
    except Exception as e:
        logger.error(f"Error during Asana integration: {e}")
        return None

def integrate_asana_for_goal(asana_access_token, goal_id, okr_id):
    try:
        workspaces = get_workspaces(asana_access_token)

        if workspaces:
            workspace_id = workspaces[0]["gid"]
            teams = get_teams_in_workspace(asana_access_token, workspace_id)
            new_goal = Goal.objects.get(goal_id=goal_id)
            if teams:
                team_id = teams[0]["gid"]
                asana_project_id = create_asana_project(
                    asana_access_token, new_goal.title, workspace_id, new_goal.description, team_id
                )

                if asana_project_id:
                    new_goal.asana_project_id = asana_project_id
                    new_goal.save()

                    sections = get_project_sections(asana_project_id, asana_access_token)
                    if sections:
                        for section in sections.get("data", []):
                            if section["name"] == "Untitled Section":
                                delete_section(section["gid"], asana_access_token)

                    to_do_section = create_asana_section(asana_access_token, asana_project_id, "To Do")
                    doing_section = create_asana_section(asana_access_token, asana_project_id, "Doing")
                    done_section = create_asana_section(asana_access_token, asana_project_id, "Done")
                    sections_response = get_project_sections(new_goal.asana_project_id, asana_access_token)
                    if sections_response:
                        
                        sections = sections_response.get("data", [])
                        to_do_section_id = next((section["gid"] for section in sections if section["name"].lower() == "to do"), None)
                        if to_do_section_id:
                            new_okr = okr.objects.filter(goal_id=goal_id)
                            for okrs in new_okr:
                                task_id = create_asana_task(
                                    asana_access_token,
                                    new_goal.asana_project_id,
                                    to_do_section_id,  
                                    okrs.title,
                                    okrs.description
                                )
                                if task_id:
                                    okrs.asana_task_id = task_id
                                    okrs.save()
                                    new_key_results = key_results.objects.filter(okr_id=okr_id)
                                    if okrs.asana_task_id:
                                        for kr in new_key_results:
                                            subtask_id = create_asana_subtask(asana_access_token, okrs.asana_task_id, kr.title, kr.description) 
                                            if subtask_id:
                                                kr.asana_subtask_id = subtask_id
                                                kr.save()
                    try:
                        callback_url = settings.ASANA_CALLBACK_URL 
                        create_asana_webhook(asana_access_token, asana_project_id, callback_url)
                    except Exception as e:
                        logger.error(f"Error setting up Asana webhook: {e}")
                        return None
    except Exception as e:
        logger.error(f"Error during Asana integration: {e}")
        return None


def integrate_asana_for_okr(asana_access_token, goal_id):
    goal_instance = Goal.objects.get(goal_id=goal_id)
    sections_response = get_project_sections(goal_instance.asana_project_id, asana_access_token)
    if sections_response:
        sections = sections_response.get("data", [])
        to_do_section_id = next((section["gid"] for section in sections if section["name"].lower() == "to do"), None)
        
        if to_do_section_id:
            new_okr = okr.objects.filter(goal_id=goal_id)
            for okrs in new_okr:
                task_id = create_asana_task(
                    asana_access_token,
                    goal_instance.asana_project_id,
                    to_do_section_id,  
                    okrs.title,
                    okrs.description
                )
                if task_id:
                    okrs.asana_task_id = task_id
                    okrs.save()
                    new_key_results = key_results.objects.filter(okr_id=okrs.okr_id)
                    if okrs.asana_task_id:
                        for kr in new_key_results:
                            subtask_id = create_asana_subtask(
                            asana_access_token, okrs.asana_task_id, kr.title, kr.description) 
                            if subtask_id:
                                kr.asana_subtask_id = subtask_id
                                kr.save()
                    else:
                        return Response({"detail": "Failed to create Asana subtask."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        logger.error(f"Failed to fetch sections for project {goal_instance.asana_project_id}: {sections_response}")

