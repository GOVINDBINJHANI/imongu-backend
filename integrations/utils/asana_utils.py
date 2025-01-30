import requests
import logging
import asana
from integrations.models import AsanaConnection
from asana.rest import ApiException
from imongu_backend_app.models import okr, key_results
logger = logging.getLogger(__name__)

def create_asana_project(access_token, project_title, workspace_id, description, team_id):
    url = "https://app.asana.com/api/1.0/projects"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    data = {
        "data": {
            "name": project_title,
            "workspace": workspace_id,
            "notes": description,
            "team": team_id  
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        logger.info("Response received: %s", response)
        if response.status_code == 201:
            return response.json()["data"]["gid"]  
        else:
            logger.error("Failed to create Asana project: %s", response.text)
            return None
    except Exception as e:
        logger.exception("Error while creating Asana project")
        return None

def update_asana_project(user_asana_token, title, asana_project_id):
    try:
        configuration = asana.Configuration()
        configuration.access_token = user_asana_token.access_token
        api_client = asana.ApiClient(configuration)
        projects_api_instance = asana.ProjectsApi(api_client) 
        body = {
            "data": {
                "name": title  
            }
        }
        project_gid = asana_project_id 
        api_response = projects_api_instance.update_project(body, project_gid, opts= None)
    except ApiException as e:
        raise Exception(f"Asana API error: {str(e)}")
    
def get_workspaces(access_token):
    url = "https://app.asana.com/api/1.0/workspaces"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        logger.debug("Using access token: %s", access_token[:10] + "..." if access_token else "None")
        response = requests.get(url, headers=headers)
        logger.info("Response status code: %d", response.status_code)
        logger.debug("Response body: %s", response.text)
        if response.status_code == 200:
            workspaces = response.json()["data"]
            logger.info("Workspaces fetched: %s", workspaces)
            return workspaces
        elif response.status_code == 401:
            logger.error("Unauthorized. Check access token and permissions.")
            return None
        else:
            logger.error("Failed to fetch workspaces: %s", response.text)
            return None
    except Exception as e:
        logger.exception("Error while fetching workspaces")
        return None


def get_teams_in_workspace(access_token, workspace_id):
    url = f"https://app.asana.com/api/1.0/teams?workspace={workspace_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            teams = response.json()["data"]
            logger.info("Teams fetched: %s", teams)
            return teams  
        else:
            logger.error("Failed to fetch teams: %s", response.text)
            return None
    except Exception as e:
        logger.exception("Error while fetching teams")
        return None



def create_asana_section(access_token, project_id, section_name):
    url = f"https://app.asana.com/api/1.0/projects/{project_id}/sections"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {"data": {"name": section_name}}  

    try:
        response = requests.post(url, headers=headers, json=payload)
        logger.debug(f"Section creation response: {response.text}")
        response.raise_for_status()  
        section_gid = response.json()["data"]["gid"]
        return section_gid
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTPError creating Asana section '{section_name}': {http_err}")
        logger.error(f"Response content: {response.text}")
    except Exception as e:
        logger.exception(f"Error creating Asana section '{section_name}': {e}")
    return None


def delete_asana_project(asana_connection, project_gid):
    if not asana_connection:
        logger.warning("Asana connection not found for the user. Cannot delete the Asana project.")
        return False  # Indicate failure to delete the project

    try:
        configuration = asana.Configuration()
        configuration.access_token = asana_connection.access_token  
        api_client = asana.ApiClient(configuration)
        projects_api_instance = asana.ProjectsApi(api_client)
        api_response = projects_api_instance.delete_project(project_gid)
    except ApiException as e:
        logger.error(f"Exception when calling ProjectsApi->delete_project: {e}")
        return False  # Indicate failure to delete the project



def create_asana_task(access_token, project_id, section_id, task_name, task_description=""):
    url = "https://app.asana.com/api/1.0/tasks"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "data": {
            "name": task_name,
            "notes": task_description,
            "projects": [project_id],  
            "section": section_id     
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  
        return response.json()["data"]["gid"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating Asana task '{task_name}': {e}")
        logger.error(f"Response content: {response.text}")
    return None


def delete_asana_task(asana_connection, task_gid):
    try:
        configuration = asana.Configuration()
        configuration.access_token = asana_connection.access_token
        api_client = asana.ApiClient(configuration)
        tasks_api_instance = asana.TasksApi(api_client)
        api_response = tasks_api_instance.delete_task(task_gid)
        logger.info(f"Task {task_gid} deleted successfully in Asana.")
    except ApiException as e:
        logger.error(f"Exception when calling TasksApi->delete_task: {e}\n")



def update_asana_task(asana_connection, task_gid, update_data):
    try:
        configuration = asana.Configuration()
        configuration.access_token = asana_connection.access_token
        api_client = asana.ApiClient(configuration)
        tasks_api_instance = asana.TasksApi(api_client)
        update_payload = {
            'data': update_data
        }
        
        api_response = tasks_api_instance.update_task(update_payload, task_gid, opts=None)
        logger.info(f"Task {task_gid} updated successfully in Asana.")
    except ApiException as e:
        logger.error(f"Exception when calling TasksApi->update_task: {e}\n")


def create_asana_subtask(access_token, task_id, subtask_title, subtask_description=""):

    url = "https://app.asana.com/api/1.0/tasks"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "data": {
            "name": subtask_title,
            "notes": subtask_description,
            "parent": task_id  
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  
        return response.json()["data"]["gid"]  
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating Asana subtask '{subtask_title}': {e}")
        if response is not None:
            logger.error(f"Response content: {response.text}")
    return None

    
def get_project_sections(project_id, access_token):
    """
    Fetch sections of a project using Asana API.
    """
    try:
        url = f"https://app.asana.com/api/1.0/projects/{project_id}/sections"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching sections for project {project_id}: {e}")
        return None


def delete_section(section_id, access_token):
    url = f"https://app.asana.com/api/1.0/sections/{section_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.delete(url, headers=headers)
    if response.status_code == 200 or response.status_code == 204:
        logger.info(f"Section {section_id} deleted successfully.")
    else:
        logger.info(f"Error deleting section: {response.text}")


def create_asana_webhook(asana_access_token, asana_project_id, callback_url):
    headers = {
        'Authorization': f'Bearer {asana_access_token}',
        'Content-Type': 'application/json',
    }
    data = {
        "data": {
            "resource": asana_project_id,
            "target": callback_url,
        }
    }
    url = "https://app.asana.com/api/1.0/webhooks"
    try:
        response = requests.post(url, headers=headers, json=data)  
        response.raise_for_status() 
        logger.info(f"Webhook created successfully: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        error_message = e.response.text if e.response else str(e)
        logger.info(f"Error creating webhook: {error_message}")
        return {"error": error_message}

def update_key_result_on_subtask_completion(task_id, resource_subtype):
    try:
        key_result = key_results.objects.get(asana_subtask_id=task_id)
        if resource_subtype == "marked_incomplete":
            key_result.current_number = key_result.initial_number
            key_result.overall_gain = 0
            logger.info(f"Setting overall_gain to 0 for subtask {task_id}")
        else:
            key_result.current_number = key_result.target_number
            key_result.overall_gain = 100
            logger.info(f"Setting overall_gain to 100 for subtask {task_id}")

        key_result.save()

        okr_instance = key_result.okr_id
        okr_instance.average_gain = calculate_okr_average_gain(okr_instance)
        okr_instance.save()

        goal_instance = okr_instance.goal_id
        goal_instance.average_gain = calculate_goal_average_gain(goal_instance)
        goal_instance.save()

        logger.info(f"Key Result, OKR, and Goal updated for subtask {task_id}")

    except key_results.DoesNotExist:
        logger.warning(f"No KeyResult entry found for subtask {task_id}")
    except Exception as e:
        logger.error(f"Error updating KeyResult for subtask {task_id}: {e}")


def update_okr_progress_on_task_status_change(task_id, status):
    try:
        okr_instance = okr.objects.get(asana_task_id=task_id)
        if status == "To Do":
            okr_instance.average_gain = 0
        elif status == "Doing":
            okr_instance.average_gain = 50
        elif status == "Done":
            okr_instance.average_gain = 100
            for kr in okr_instance.key_results.all():
                kr.current_number = kr.target_number
                kr.overall_gain = 100
                kr.save()

        okr_instance.save()
        goal_instance = okr_instance.goal_id
        goal_instance.average_gain = calculate_goal_average_gain(goal_instance)
        goal_instance.save()

        logger.info(f"OKR and Goal progress updated for task {task_id} with status {status}")

    except okr.DoesNotExist:
        logger.warning(f"No OKR entry found for task {task_id}")
    except Exception as e:
        logger.error(f"Error updating OKR progress for task {task_id}: {e}")


def calculate_okr_average_gain(okr_instance):
    key_results = okr_instance.key_results.all()
    total_gain = sum(kr.overall_gain for kr in key_results)
    return total_gain / key_results.count() if key_results.exists() else 0


def calculate_goal_average_gain(goal_instance):
    okrs = goal_instance.okr_set.all()
    total_gain = sum(okr.average_gain for okr in okrs)
    return total_gain / okrs.count() if okrs.exists() else 0


def get_section_name(section_gid):
    try:
        asana_connection = AsanaConnection.objects.first()
        if not asana_connection:
            raise ValueError("Asana access token not found in the database.")
        access_token = asana_connection.access_token

        url = f"https://app.asana.com/api/1.0/sections/{section_gid}"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        return data.get("data", {}).get("name", "")
    except Exception as e:
        logger.error(f"Failed to fetch section name for GID {section_gid}: {e}")
        return ""



def handle_asana_integration(login_user_id, goal_instance, new_okr=None, new_key_result=None):
    """
    Handles Asana integration for goals, OKRs, and key results.
    """
    try:
        asana_connection = AsanaConnection.objects.get(user=login_user_id)
    except AsanaConnection.DoesNotExist:
        return {"status": False, "error": "Asana connection not found"}
    
    asana_access_token = asana_connection.access_token
    
    if new_okr:
        if goal_instance.asana_project_id:
            sections_response = get_project_sections(goal_instance.asana_project_id, asana_access_token)
            if sections_response:
                sections = sections_response.get("data", [])
                to_do_section_id = next((section["gid"] for section in sections if section["name"].lower() == "to do"), None)

                if to_do_section_id:
                    task_id = create_asana_task(
                        asana_access_token,
                        goal_instance.asana_project_id,
                        to_do_section_id,
                        new_okr.title,
                        new_okr.description
                    )
                    if task_id:
                        new_okr.asana_task_id = task_id
                        new_okr.save()

                        for kr in key_results.objects.filter(okr_id=new_okr.okr_id):
                            subtask_id = create_asana_subtask(
                                asana_access_token, new_okr.asana_task_id, kr.title, kr.description
                            )
                            if subtask_id:
                                kr.asana_subtask_id = subtask_id
                                kr.save()
    elif new_key_result:
        if new_key_result.okr_instance.asana_task_id:
            subtask_id = create_asana_subtask(
                asana_access_token, new_key_result.okr_instance.asana_task_id, new_key_result.title, new_key_result.description
            )
            if subtask_id:
                new_key_result.asana_subtask_id = subtask_id
                new_key_result.save()

    return {"status": True}