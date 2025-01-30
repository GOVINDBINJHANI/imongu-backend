from django_elasticsearch_dsl import Document, fields,Keyword
from django_elasticsearch_dsl.registries import registry
from imongu_backend_app.models import Goal, company,goal_owners,okr,result_owner,owners,key_results, employee, User, team_Table, Reports, Role
from elasticsearch_dsl import Completion
from django.db.models import Q
from django.dispatch import receiver

@registry.register_document
class GoalDocument(Document):
    company_id = fields.ObjectField(properties={
        "company_id": fields.TextField(),
        "company_name": fields.TextField(),
    })

    # document_type = Keyword(default='goal')
    class Index:
        name = 'goals'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    class Django:
        model = Goal
        fields = [
            'title',
            'description',
            'goal_id',
        ]
        related_models = [company]
    def get_instances_from_related(self, related_instance):
        return Goal.objects.filter(company_id=related_instance)
    

    # def get_goal_owners_data(self, instance):
    #     # Query related goal_owners based on goal_id
    #     goal_owners_data = goal_owners.objects.filter(goal_id=instance.goal_id)

    #     # Extract relevant data from goal_owners and return as lists
    #     goal_owner_ids = [owner.goal_owner_id for owner in goal_owners_data]
    #     user_ids = [owner.user_id for owner in goal_owners_data]
    #     team_ids = [owner.team_id for owner in goal_owners_data]

    #     return {
    #         "goal_owner_ids": goal_owner_ids,
    #         "user_ids": user_ids,
    #         "team_ids": team_ids
    #     }

@registry.register_document
class OKRDocument(Document): 
    company_id = fields.ObjectField(properties={
        "company_id": fields.KeywordField(),
        "company_name": fields.TextField(),
    })

    class Index:
        name = 'okrs'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }

    class Django:
        model = okr
        fields = [
            'okr_id',
            'title',
            'description',
        ]
        related_models = [Goal,company]
        
    def prepare_company_id(self, instance):
        # Assuming that 'goal' is the related name in the okr model
        goal_instance = instance.goal_id
        if goal_instance:
            company_instance = goal_instance.company_id
            if company_instance:
                return {
                    'company_id': str(company_instance.company_id),
                    'company_name': company_instance.company_name,
                }
        return None

    def get_queryset(self):
        return okr.objects.all().select_related('goal_id__company_id')

    def get_instances_from_related(self, related_instance):
        if isinstance(related_instance, Goal):
            return related_instance.okr_set.all()

        return None


@registry.register_document
class EmployeeDocument(Document):
    user_id = fields.ObjectField(properties={
        "user_id": fields.IntegerField(),
        "username": fields.TextField(),
        "email": fields.TextField(),
        "profile_image": fields.TextField(),
    })
    company_id = fields.ObjectField(properties={
        "company_id": fields.KeywordField(),
        "company_name": fields.TextField(),
    })
    role = fields.ObjectField(properties={
        "role_id": fields.IntegerField(),
        "role_name": fields.TextField(),
    })

    class Index:
        name = "employees"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }

    class Django:
        model = employee
        fields = [
            "employee_id",
        ]

        related_models = [User, company, Role]
    

    def get_queryset(self):
        return employee.objects.all().select_related('user_id', 'company_id')

    def get_instances_from_related(self, related_instance):
        if isinstance(related_instance, company):
            return related_instance.employee_set.first()
        elif isinstance(related_instance, User):
            return related_instance.employee_set.first()

        return None

@registry.register_document
class ReportDocument(Document):
    company_id = fields.ObjectField(properties={
        "company_id": fields.KeywordField(),
        "company_name": fields.TextField(),
    })
    
    class Index:
        name = 'reports'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    
    class Django:
        model = Reports
        fields = [
            "report_id",
            "name",
            "type"
        ] 
        related_models = [company]   
    def get_instances_from_related(self, related_instance):
        return Reports.objects.filter(company_id=related_instance)

@registry.register_document
class TeamTableDocument(Document):
    company_id = fields.ObjectField(properties={
        "company_id": fields.KeywordField(),
        "company_name": fields.KeywordField(),
    })

    class Index:
        name = 'teams'
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }

    class Django:
        model = team_Table
        fields = [
            "team_id",
            "team_name",
        ]
        related_models = [company]

    def get_instances_from_related(self, related_instance):
        # Retrieve team tables filtered by company_id
        return team_Table.objects.filter(company_id=related_instance.company_id)
    
    
@registry.register_document
class KeyResultsDocument(Document):
    company_id = fields.ObjectField(properties={
        "company_id": fields.KeywordField(),
        "company_name": fields.TextField(),
    }) 
    class Index:
        name = 'key_results'
        settings = {'number_of_shards': 1, 
                    'number_of_replicas': 0}

    class Django:
        model = key_results

        fields = [
            'key_id',
            'title',
            'description',
        ]

        related_models = [Goal, company, okr]
        
    def prepare_company_id(self, instance):
    # Assuming that 'okr_id' is the ForeignKey in the key_results model
        okr_instance = instance.okr_id
        if okr_instance:
            goal_instance = okr_instance.goal_id
            if goal_instance:
                company_instance = goal_instance.company_id
                if company_instance:
                    return {
                    'company_id': str(company_instance.company_id),
                    'company_name': company_instance.company_name,
                    }
        return None    

    def get_queryset(self):
        return key_results.objects.all().select_related('okr_id__goal_id__company_id', 'okr_id__goal_id').prefetch_related('okr_id')

    def get_instances_from_related(self, related_instance):
        if isinstance(related_instance, Goal):
            company_id = related_instance.company_id_id  
            return key_results.objects.filter(okr_id__goal_id__company_id=company_id)
        return None