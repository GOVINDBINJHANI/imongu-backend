import json ,requests 
from imongu_backend_app.models import JiraConnection

def validate_jira(company_id):
    try:
        jira_cred = JiraConnection.objects.get(company_id=company_id)
        return True
    except JiraConnection.DoesNotExist:
        return False

def create_epic(summary, description , company_id):
        jira_cred = JiraConnection.objects.get(company_id=company_id)
        project_key = jira_cred.project_key
        base_url = jira_cred.sub_domain_url
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        auth = (jira_cred.username, jira_cred.api_token)
        create_issue_endpoint = f"{base_url}/rest/api/3/issue"
        epic_data = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]},
                "issuetype": {"name": "Epic"}
            }
        }
        payload = json.dumps(epic_data)
        response = requests.post(create_issue_endpoint, headers=headers, auth=auth, data=payload)
        if response.status_code == 201:
            data =  response.json()
            epic_key = data['key']
            return epic_key
        else:
            return None

def create_story(epic_key, summary, description,company_id):
    jira_cred = JiraConnection.objects.get(company_id=company_id)
    project_key = jira_cred.project_key
    base_url = jira_cred.sub_domain_url
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    auth = (jira_cred.username, jira_cred.api_token)
    create_issue_endpoint = f"{base_url}/rest/api/3/issue"
    issue_payload = {
        "fields": {
            "project": {
                "key": project_key
            },
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {
                "name": "Story"
            },
            "parent": {
                "key": epic_key
            }
        }
    }
    response = requests.post(create_issue_endpoint, headers=headers, auth=auth, data=json.dumps(issue_payload))
    if response.status_code == 201:
        data = response.json()
        story_key = data.get('key')
        return story_key
    else:
        return None

def create_subtask(story_key, subtask_summary, subtask_description,company_id):
    payload = {
        "fields": {
            "project": {"key": story_key.split("-")[0]},
            "summary": subtask_summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": subtask_description}],
                    }
                ],
            },
            "issuetype": {"name": "Subtask"},
            "parent": {"key": story_key},
        }
    }
    payload_json = json.dumps(payload)
    jira_cred = JiraConnection.objects.get(company_id=company_id)
    base_url = jira_cred.sub_domain_url
    headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    auth = (jira_cred.username, jira_cred.api_token)
    url = f"{base_url}/rest/api/3/issue/"
    response = requests.post(url, headers=headers, data=payload_json, auth=auth)
    if response.status_code == 201:
        data = response.json()
        subtask_key = data.get('key')
        return subtask_key
    else:
        return None
