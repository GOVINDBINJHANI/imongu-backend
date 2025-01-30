import os
import sys
import django
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "imongu_backend.settings")
django.setup()

from django.core.management.base import BaseCommand
from datetime import datetime

from imongu_backend_app.models import Feature, Activity ,Template, Question, QuestionTitle

# Define the data for features
feature_data = [
    {'id': 6, 'name': 'Goal'},
    {'id': 7, 'name': 'Objective'},
    {'id': 8, 'name': 'Key-Results'},
    {'id': 9, 'name': 'Teams'},
    {'id': 10, 'name': 'Integrations'},
    {'id': 12, 'name': 'Schedules'},
    {'id': 13, 'name': 'Templates'},
    {'id': 15, 'name': 'KPI-Metrics'},
    {'id': 16, 'name': 'Organizational-Hierarchy'},
    {'id': 17, 'name': 'Team-Collabs'},
    {'id': 18, 'name': 'Chatbot'},
    {'id': 20, 'name': 'Invite-Members'},
    {'id': 21, 'name': 'Cascade-View'},
    {'id': 22, 'name': 'Tree-View'},
    {'id': 23, 'name': 'Employees'},
]

# Define the data for activities, connected to features by feature_id
activity_data = [
    {'id': 5, 'name': 'Create', 'feature_id': 6},
    {'id': 6, 'name': 'View', 'feature_id': 6},
    {'id': 7, 'name': 'Update', 'feature_id': 6},
    {'id': 8, 'name': 'Delete', 'feature_id': 6},
    {'id': 9, 'name': 'Count', 'feature_id': 6},
    {'id': 10, 'name': 'Create', 'feature_id': 7},
    {'id': 11, 'name': 'View', 'feature_id': 7},
    {'id': 12, 'name': 'Update', 'feature_id': 7},
    {'id': 13, 'name': 'Delete', 'feature_id': 7},
    {'id': 14, 'name': 'Create', 'feature_id': 8},
    {'id': 15, 'name': 'View', 'feature_id': 8},
    {'id': 16, 'name': 'Update', 'feature_id': 8},
    {'id': 17, 'name': 'Delete', 'feature_id': 8},
    {'id': 18, 'name': 'Create', 'feature_id': 9},
    {'id': 19, 'name': 'Update', 'feature_id': 9},
    {'id': 20, 'name': 'Delete', 'feature_id': 9},
    {'id': 21, 'name': 'Count', 'feature_id': 9},
    {'id': 22, 'name': 'Allow', 'feature_id': 10},
    {'id': 26, 'name': 'Create', 'feature_id': 12},
    {'id': 30, 'name': 'Create', 'feature_id': 13},
    {'id': 36, 'name': 'Create', 'feature_id': 15},
    {'id': 37, 'name': 'Delete', 'feature_id': 15},
    {'id': 38, 'name': 'View', 'feature_id': 16},
    {'id': 39, 'name': 'Invite', 'feature_id': 17},
    {'id': 43, 'name': 'Allow', 'feature_id': 18},
    {'id': 48, 'name': 'Invite', 'feature_id': 20},
    {'id': 49, 'name': 'Allow', 'feature_id': 21},
    {'id': 50, 'name': 'Allow', 'feature_id': 22},
    {'id': 51, 'name': 'Delete', 'feature_id': 23},
]

# Populate Feature table
def populate_features():
    with tqdm(total=len(feature_data), desc='Populating features', unit="Feature") as pbar:
        for feature in feature_data:
            Feature.objects.get_or_create(id=feature['id'], feature_name=feature['name'])
            pbar.update(1)

# Populate Activity table
def populate_activities():
    with tqdm(total=len(activity_data), desc='Populating activities', unit="Activity") as pbar:
        for activity in activity_data:
            feature_instance = Feature.objects.get(id=activity['feature_id'])
            Activity.objects.get_or_create(
                id=activity['id'],
                activity_name=activity['name'],
                feature=feature_instance
            )
            pbar.update(1)






class Command(BaseCommand):
    help = "Populate the database with initial data for templates, questions, and question titles."

    def handle(self, *args, **kwargs):
        # Data for Template
        template_data = [
            (7, "Weekly Templates are focused on discoveries and recent learnings early on by a direct report.", "Weekly Template", "weekly_template", "2024-09-09 08:20:22.000035", "2024-09-09 08:20:22.000035", 1),
            (8, "The aim of the Monthly Template is to capture and adjust for more broader and long term actions compared to weekly meetings.", "Monthly Template", "monthly_template", "2024-09-09 08:20:43.904990", "2024-09-09 08:20:43.906659", 1),
            (9, "Quarterly templates are used at crucial points for assessing performance, reviewing for any possible strategic realignments before the year ends, and planning for the upcoming quarters. These templates often focus on a deeper dive into the progress made.", "Quarterly Template", "quarterly_template", "2024-09-09 08:20:57.202445", "2024-09-09 08:20:57.202445", 1)
        ]

        for tpl in template_data:
            Template.objects.update_or_create(
                id=tpl[0],
                defaults={
                    'description': tpl[1],
                    'template_title': tpl[2],
                    'template_type': tpl[3],
                    'created_at': datetime.strptime(tpl[4], "%Y-%m-%d %H:%M:%S.%f"),
                    'updated_at': datetime.strptime(tpl[5], "%Y-%m-%d %H:%M:%S.%f"),
                }
            )

        question_title_data = [
            (47, 'Reviewing Progress', 7),
            (48, 'Addressing Challenges', 7),
            (49, 'Next Steps', 7),
            (50, 'Alignment and Support', 7),
            (51, 'Feedback and Reflection', 7),
            (52, 'Long-term Focus', 7),
            (53, 'Reviewing Progress', 8),
            (54, 'Analyzing Performance', 8),
            (55, 'Strategy and Adjustment', 8),
            (56, 'Resource and Support Needs', 8),
            (57, 'Reflecting on Processes', 8),
            (58, 'Future Planning', 8),
            (59, 'Alignment and Engagement', 8),
            (60, 'Feedback and Communication', 8),
            (61, 'Overall Performance Review', 9),
            (62, 'Deep Dive into OKRs', 9),
            (63, 'Strategic Alignment and Adjustments', 9),
            (64, 'Resource and Support Evaluation', 9),
            (65, 'Process Improvement', 9),
            (66, 'Future Planning', 9),
            (67, 'Performance and Feedback', 9),
            (68, 'Engagement and Motivation', 9),
            (69, 'Long-term Vision', 9)
        ]

        # Populate QuestionTitle table
        with tqdm(total=len(question_title_data), desc='Populating question titles', unit="Title") as pbar:
            for title_id, title, template_id in question_title_data:
                QuestionTitle.objects.update_or_create(
                    id=title_id,
                    defaults={
                        'question_title': title,
                        'template_id': template_id
                    }
                )
                pbar.update(1)

        # Data for Questions
        question_data = [
            (101, 'What progress have you made toward your OKRs this week?', '2024-09-09 08:20:22.596363', '2024-09-09 08:20:22.596363', 47, 7),
            (102, 'Were there any Key Results achieved?', '2024-09-09 08:20:22.876729', '2024-09-09 08:20:22.876729', 47, 7),
            (103, 'Did you encounter any challenges or obstacles?', '2024-09-09 08:20:23.207814', '2024-09-09 08:20:23.207814', 47, 7),
            (104, 'What are the main reasons for any delays or setbacks?', '2024-09-09 08:20:23.750413', '2024-09-09 08:20:23.750413', 48, 7),
            (105, 'How can I or the team assist in overcoming these challenges?', '2024-09-09 08:20:24.031095', '2024-09-09 08:20:24.031095', 48, 7),
            (106, 'What are your priorities for the upcoming week?', '2024-09-09 08:20:24.605576', '2024-09-09 08:20:24.605576', 49, 7),
            (107, 'Are there any changes needed to your current OKRs or strategies?', '2024-09-09 08:20:24.870108', '2024-09-09 08:20:24.870108', 49, 7),
            (108, 'How do your current tasks align with the broader company goals?', '2024-09-09 08:20:25.460617', '2024-09-09 08:20:25.460617', 50, 7),
            (109, 'Is there any additional support or resources you need?', '2024-09-09 08:20:25.770219', '2024-09-09 08:20:25.770219', 50, 7),
            (110, 'What have you learned this week that could improve our approach or processes?', '2024-09-09 08:20:26.387418', '2024-09-09 08:20:26.387418', 51, 7),
            (111, 'How do you feel about your progress and workload?', '2024-09-09 08:20:26.683341', '2024-09-09 08:20:26.683341', 51, 7),
            (112, 'Are there any adjustments needed to long-term goals based on current progress?', '2024-09-09 08:20:27.307443', '2024-09-09 08:20:27.307443', 52, 7),
            (113, 'What are your thoughts on our overall progress toward achieving the broader objectives?', '2024-09-09 08:20:27.620547', '2024-09-09 08:20:27.620547', 52, 7),
            (114, 'What were your major accomplishments this month?', '2024-09-09 08:20:44.422747', '2024-09-09 08:20:44.422747', 53, 8),
            (115, 'Which Key Results have you made progress on or completed?', '2024-09-09 08:20:44.678501', '2024-09-09 08:20:44.678501', 53, 8),
            (116, 'Were there any notable challenges or setbacks?', '2024-09-09 08:20:44.948854', '2024-09-09 08:20:44.948854', 53, 8),
            (117, 'How do this month\'s results compare to previous months?', '2024-09-09 08:20:45.474091', '2024-09-09 08:20:45.474091', 54, 8),
            (118, 'What contributed to any successes or failures this month?', '2024-09-09 08:20:45.830754', '2024-09-09 08:20:45.830754', 54, 8),
            (119, 'Are there any changes needed to your OKRs for the next month?', '2024-09-09 08:20:46.762609', '2024-09-09 08:20:46.762609', 55, 8),
            (120, 'Do we need to realign any objectives to better fit current priorities or challenges?', '2024-09-09 08:20:47.068663', '2024-09-09 08:20:47.068663', 55, 8),
            (121, 'Have you identified any gaps or needs for additional resources or support?', '2024-09-09 08:20:47.665860', '2024-09-09 08:20:47.665860', 56, 8),
            (122, 'What can I or the team do to help you achieve your OKRs more effectively?', '2024-09-09 08:20:48.002120', '2024-09-09 08:20:48.002120', 56, 8),
            (123, 'What have you learned this month that could improve our approach or processes?', '2024-09-09 08:20:48.719846', '2024-09-09 08:20:48.719846', 57, 8),
            (124, 'Are there any best practices or successful strategies you can share?', '2024-09-09 08:20:49.245819', '2024-09-09 08:20:49.245819', 57, 8),
            (125, 'What are your key objectives for the next month?', '2024-09-09 08:20:49.843439', '2024-09-09 08:20:49.843439', 58, 8),
            (126, "What are your long-term goals or projects you're working towards?", '2024-09-09 08:20:50.145149', '2024-09-09 08:20:50.145149', 58, 8),
            (127, 'How do your current objectives align with the company\'s strategic goals?', '2024-09-09 08:20:50.755878', '2024-09-09 08:20:50.755878', 59, 8),
            (128, 'How satisfied are you with your progress and the current direction?', '2024-09-09 08:20:51.056519', '2024-09-09 08:20:51.056519', 59, 8),
            (129, "Is there anything you'd like to discuss or need feedback on?", '2024-09-09 08:20:51.678039', '2024-09-09 08:20:51.678039', 60, 8),
            (130, 'Do you have any feedback for me or the organization on how we can improve?', '2024-09-09 08:20:51.928353', '2024-09-09 08:20:51.928353', 60, 8),
            (131, 'What were the major accomplishments this quarter?', '2024-09-09 08:20:57.867863', '2024-09-09 08:20:57.867863', 61, 9),
            (132, 'How do the results this quarter compare to the goals and OKRs set at the beginning of the period?', '2024-09-09 08:20:58.142520', '2024-09-09 08:20:58.142520', 61, 9),
            (133, 'What were the key challenges or obstacles faced this quarter, and how were they addressed?', '2024-09-09 08:20:58.432007', '2024-09-09 08:20:58.432007', 61, 9),
            (134, 'Which Key Results were fully achieved, and which fell short?', '2024-09-09 08:20:59.154441', '2024-09-09 08:20:59.154441', 62, 9),
            (135, 'What factors contributed to the success or shortfall in these Key Results?', '2024-09-09 08:20:59.458908', '2024-09-09 08:20:59.458908', 62, 9),
            (136, 'How well did the OKRs align with the company\'s overall strategic goals this quarter?', '2024-09-09 08:21:00.029454', '2024-09-09 08:21:00.029454', 63, 9),
            (137, 'Based on this quarter\'s performance, are there any necessary adjustments to the OKRs for the upcoming quarter?', '2024-09-09 08:21:00.380519', '2024-09-09 08:21:00.380519', 63, 9),
            (138, 'What strategic initiatives or changes are planned for the next quarter?', '2024-09-09 08:21:00.691820', '2024-09-09 08:21:00.691820', 63, 9),
            (139, 'Were there any resource constraints or needs that impacted performance this quarter?', '2024-09-09 08:21:01.301999', '2024-09-09 08:21:01.301999', 64, 9),
            (140, 'What support or resources will be necessary to achieve the goals for the next quarter?', '2024-09-09 08:21:01.570891', '2024-09-09 08:21:01.570891', 64, 9),
            (141, 'What lessons were learned this quarter that can improve our approach or processes?', '2024-09-09 08:21:02.092650', '2024-09-09 08:21:02.100643', 65, 9),
            (142, 'Are there any process changes or improvements needed to better support your objectives?', '2024-09-09 08:21:02.362940', '2024-09-09 08:21:02.362940', 65, 9),
            (143, 'What are the key objectives for the upcoming quarter?', '2024-09-09 08:21:02.904978', '2024-09-09 08:21:02.904978', 66, 9),
            (144, 'How do these upcoming objectives fit into the broader annual or long-term strategy?', '2024-09-09 08:21:03.165031', '2024-09-09 08:21:03.165031', 66, 9),
            (145, 'How do you assess your own performance and progress this quarter?', '2024-09-09 08:21:03.762862', '2024-09-09 08:21:03.762862', 67, 9),
            (146, 'What feedback do you have for me or the organization to help improve our support and processes?', '2024-09-09 08:21:04.029111', '2024-09-09 08:21:04.029111', 67, 9),
            (147, 'How satisfied are you with your role and progress?', '2024-09-09 08:21:04.680304', '2024-09-09 08:21:04.680304', 68, 9),
            (148, 'Are there any motivational or developmental opportunities you\'d like to pursue in the next quarter?', '2024-09-09 08:21:04.963733', '2024-09-09 08:21:04.963733', 68, 9),
            (149, 'How do your current achievements and challenges inform your long-term career or project goals?', '2024-09-09 08:21:05.609038', '2024-09-09 08:21:05.609038', 69, 9),
            (150, 'What are your thoughts on the company\'s direction and how it affects your work and goals?', '2024-09-09 08:21:05.862951', '2024-09-09 08:21:05.862951', 69, 9)
        ]

        # Populate Question table
        with tqdm(total=len(question_data), desc='Populating questions', unit="Question") as pbar:
            for q_id, text, created, updated, title_id, template_id in question_data:
                Question.objects.update_or_create(
                    id=q_id,
                    defaults={
                        'text': text,
                        'created_at': datetime.strptime(created, "%Y-%m-%d %H:%M:%S.%f"),
                        'updated_at': datetime.strptime(updated, "%Y-%m-%d %H:%M:%S.%f"),
                        'question_title_id': title_id,
                        'template_id': template_id
                    }
                )
                pbar.update(1)

        self.stdout.write(self.style.SUCCESS("Successfully populated templates, questions, and question titles"))



# Run the functions to populate data
populate_features()
populate_activities()
