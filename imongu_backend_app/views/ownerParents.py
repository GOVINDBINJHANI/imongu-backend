from rest_framework import status
from imongu_backend_app.models import employee,Goal, okr,key_results,team_Table
from imongu_backend_app.Serializers import employeeserializers,GoalSerializers, okrserializers,key_resultsserializers
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from imongu_backend_app.utils.owners import *
from imongu_backend_app.utils.helper import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId


class assignOwners(GenericAPIView):
    permission_classes = [IsValidUser]

    def get(self,request):
        company_id = request.query_params.get('company_id')
        type = request.query_params.get('type','owner')
        # print("is_department",type(is_department))
        all_data = []
        team_data = team_Table.objects.filter(company_id=company_id)
        if type=='owner':
            print('here')
            employee_data = employee.objects.filter(company_id=company_id)
            serializer = employeeserializers(employee_data,many=True)
            for emp ,user in zip(serializer.data,employee_data):
                all_data.append({"type" : "user" , "name" : user.user_id.username ,"profile_image" : user.user_id.profile_image , "id" : emp.get('user_id'),"email" : user.user_id.email})
        for team in team_data:
            all_data.append({"type" : "team" , "name" : team.team_name , "id" : team.team_id })
        return Response(all_data,status=status.HTTP_200_OK)
    
class assignParents(GenericAPIView):
    permission_classes = [IsValidUser]

    def get(self,request):
        all_goals=[]
        company_id=request.query_params.get('company_id')
        session=request.query_params.get('session','')
        queryset=Goal.objects.filter(company_id=company_id).prefetch_related( "goal_owners")      
        if session:
            goal_objs=queryset.filter(session=session)
        else:
            goal_objs=queryset
        if goal_objs:
            serializer = GoalSerializers(goal_objs, many=True)
            for goal_data in serializer.data:
                goal_dict=goal_data
                goal_id=goal_data.get('goal_id')
                okr_data=okr.objects.filter(goal_id=goal_id).prefetch_related( "owners")
                okr_serializer = okrserializers(okr_data, many=True)
                goal_dict['children'] = okr_serializer.data
                all_goals.append(goal_dict)
        return Response(all_goals)
    
class owners_view(GenericAPIView):
    permission_classes = [IsValidUser]

    def get(self,request):
        all_goal_data = {}
        all_details={}
        goal_id=request.query_params.get('goal_id')
        try:
            goals=Goal.objects.get(goal_id=goal_id)
        except Goal.DoesNotExist:
            return Response({'error': 'Goal not found'}, status=status.HTTP_404_NOT_FOUND)
        serilizer=GoalSerializers(goals)
        # goal_owners_list=goal_owner(goal_id)
        all_details=serilizer.data
        company_name = goals.company_id.company_name
        all_details['company_name']=company_name
        # all_details['owners']=goal_owners_list
        # checking their paretns 
        # parent_id = serilizer.data.get('parent_id')
        # if parent_id: 
        #     try:
        #         parent = Parents.objects.get(parent_id=parent_id)
        #         all_goal_data = get_parent(parent)
        #         all_goal_data['parent'] = True
        #         all_goal_data['parent_type'] = parent.parent_type
        #         all_details['parent_type'] = parent.parent_type
        #         all_details['child_type'] = 'goal'
        #     except Parents.DoesNotExist:
        #         goals.parent_id = None
        #         goals.save()
        #         all_goal_data['parent'] = False
        # else:
        #     all_goal_data['parent'] = False
        all_goal_data['parent'] = False
        okr_list,avg_okr_gain,okr_gains = get_list_of_okr(goal_id)
        # checking their child
        # try:
        #     childs = Parents.objects.filter(goal_id=goal_id)
        #     if childs:
        #         child_goal_gain = 0
        #         for child in childs:
        #             child_goal = get_child(child)
        #             if child_goal:
        #                 child_goal['parent_type'] = 'goal'
        #                 child_goal['child_type'] = 'goal'
        #                 child_goal_gain += child_goal['overall_gain']
        #                 okr_list.append(child_goal)
        #         all_goal_data['child'] = True
        #         all_goal_data['child_type'] = 'parent_goal'
        #         try:
        #             n = len(okr_list)   
        #             avg_okr_gain = round ((okr_gains+child_goal_gain) / n)
        #         except Exception:
        #             avg_okr_gain = 0
        # except Parents.DoesNotExist :
        #     all_goal_data['child'] = False

        all_details['children']=okr_list
        all_details['overall_gain']=avg_okr_gain
        all_goal_data['children'] = [all_details]
        return Response(all_goal_data,status=status.HTTP_200_OK)
