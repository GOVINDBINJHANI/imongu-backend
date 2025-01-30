from rest_framework import status
from imongu_backend_app.models import User,company,employee,Goal,goal_owners, okr,owners,key_results,result_owner,team_Table, team_employees,Reports
from imongu_backend_app.Serializers import TeamEmployeeSerializer,GoalSerializers, okrserializers,key_resultsserializers,TeamSerializer,ReportsSerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.db.models import Avg,Q,Count
from django.utils import timezone
import uuid
from imongu_backend_app.utils.helper import *
from imongu_backend_app.utils.users import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, validate_feature_activity_access
from imongu_backend_app.utils.s3 import pdf_to_s3_url
from imongu_backend_app.utils.report import *

class okr_statistics(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        company_id = request.data.get('company_id')
        name = request.data.get('name')
        report_type = request.data.get('type')
        user_id = GetUserId.get_user_id(request)

        try:
            company_obj = company.objects.get(company_id=company_id)
            user_obj = User.objects.get(user_id=user_id)
        except company.DoesNotExist:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        report = Reports.objects.create(report_id=str(uuid.uuid4()) , company_id=company_obj,user_id=user_obj,name=name ,type= report_type,date_created=timezone.now())
        serialze = ReportsSerializer(report)
        return Response(serialze.data,status=status.HTTP_200_OK)
    
    def get(self,request):
        company_id = request.query_params.get('company_id' , '')
        report_id = request.query_params.get('report_id' , '')
        user_id = GetUserId.get_user_id(request)
        performance_report = request.query_params.get('performance_report' ,False)
        process_report = request.query_params.get('process_report' , False)
        objective = okr.objects.filter(goal_id__company_id=company_id)
        goal_objs = Goal.objects.filter(company_id=company_id)
        key_result = key_results.objects.filter(okr_id__goal_id__company_id=company_id)
        total_goal = len(goal_objs) 
        total_okr = len(objective) 
        total_key_result = len(key_result)

        # getting the performance_report 
        if performance_report:
            Performance_report = {}
            overall_gain_goal = 0;goal_progress=0;goal_with_no_progress=0
            total_goal = len(goal_objs)
            if goal_objs:
                for goal in goal_objs:
                    goal_id = goal.goal_id
                    filtered_okrs = okr.objects.filter(goal_id=goal_id)
                    goal_gain = get_goal_progress(filtered_okrs)
                    overall_gain_goal += goal_gain
                    if goal_gain==0:
                        goal_with_no_progress += 1

                goal_progress = overall_gain_goal / total_goal   
            Performance_report['total_goal'] = total_goal
            Performance_report['avg_goal_progress'] = goal_progress
            Performance_report['goal_with_no_progress'] = goal_with_no_progress

            progress_by_user = {}
            employees = employee.objects.filter(company_id=company_id)
            if employees:
                users_goal_progress = [];users_okr_progress = []; users_key_progress = []
                for emp in employees:
                    emp_goal = {} ; emp_okr = {} ; emp_key = {}
                    emp_goal_progress = 0;key_progress=0
                    owner_user = emp.user_id
                    # getting user goal progress 
                    filtered_gaol_with_owner = Goal.objects.filter(goal_owners__user_id = owner_user,company_id=company_id)
                    if filtered_gaol_with_owner:
                        n= len(filtered_gaol_with_owner)
                        for goal in filtered_gaol_with_owner:
                            filtered_okrs = okr.objects.filter(goal_id=goal.goal_id)
                            goal_gain = get_goal_progress(filtered_okrs)
                            emp_goal_progress += goal_gain
                        emp_goal['progress'] = emp_goal_progress/n
                        emp_goal['user_id'] = owner_user.user_id
                        emp_goal['username'] = owner_user.username
                        users_goal_progress.append(emp_goal)

                    # getting user okr progress 
                    filtered_okr = okr.objects.filter(owners__user_id = owner_user,goal_id__company_id=company_id)
                    if filtered_okr:
                        okr_progress = get_goal_progress(filtered_okr) 
                        emp_okr['progress'] = okr_progress
                        emp_okr['user_id'] = owner_user.user_id
                        emp_okr['username'] = owner_user.username
                        users_okr_progress.append(emp_okr)

                    # getting user key progress 
                    filtered_key_results = key_results.objects.filter(result_owner__user_id=owner_user,okr_id__goal_id__company_id=company_id)
                    if filtered_key_results:
                        average_overall_gain = filtered_key_results.aggregate(Avg('overall_gain'))['overall_gain__avg']
                        if average_overall_gain:
                            key_progress = average_overall_gain
                        emp_key['progress'] = key_progress
                        emp_key['user_id'] = owner_user.user_id
                        emp_key['username'] = owner_user.username
                        users_key_progress.append(emp_key)
                    
                progress_by_user['goal'] = users_goal_progress
                progress_by_user['okr'] = users_okr_progress
                progress_by_user['key_result'] = users_key_progress
            Performance_report['progress_by_user'] = progress_by_user

            # getting the progress of the teams 
            teams = team_Table.objects.filter(company_id=company_id)
            progress_by_team = []
            for team in teams:
                team_id = team.team_id
                avg_goal_progress = get_avg_goalprogress_of_team(team_id)
                if avg_goal_progress != 0:
                    progress_by_team.append({"team_name" : team.team_name , "team_id" : team_id , "progress" : avg_goal_progress})
            Performance_report['progress_by_team'] = progress_by_team
            return Response(Performance_report,status=status.HTTP_200_OK)

        # getting the Process report
        if process_report:
            Process_report = {}
            Process_report['total_goal'] = total_goal
            Process_report['total_okr'] = total_okr
            Process_report['total_key_result'] = total_key_result
            people_without_goal = 0;people_without_objective = 0;people_without_key_result = 0
            
            total_employees = employee.objects.filter(company_id=company_id)
            goal_owner_user_ids = goal_owners.objects.filter(Q(goal_id__company_id=company_id) & Q(user_id__isnull=False)).values('user_id').distinct()
            objective_owner_ids = owners.objects.filter(Q(okr_id__goal_id__company_id=company_id) & Q(user_id__isnull=False)).values('user_id').distinct()
            key_result_owner_ids = result_owner.objects.filter(Q(key_id__okr_id__goal_id__company_id=company_id) & Q(user_id__isnull=False)).values('user_id').distinct()
            
            people_without_goal = total_employees.exclude(user_id__in=goal_owner_user_ids).values('user_id')
            people_without_objective = total_employees.exclude(user_id__in=objective_owner_ids).values('user_id')
            people_without_key_result = total_employees.exclude(user_id__in=key_result_owner_ids).values('user_id') 

            Process_report['people_without_goal'] = {'count' : people_without_goal.count() , 'users' : get_user_details(people_without_goal)}
            Process_report['people_without_objective'] ={'count' : people_without_objective.count(),'users' : get_user_details(people_without_objective)}
            Process_report['people_without_key_result'] = { 'count' : people_without_key_result.count(),'users' : get_user_details(people_without_key_result)}

            goal_without_objective = goal_objs.exclude(goal_id__in=okr.objects.values('goal_id'))
            Process_report['goal_without_objective'] = {'count' : len(goal_without_objective) , 'goals' : GoalSerializers(goal_without_objective , many=True).data}
            
            objective_without_keyresult = objective.exclude(okr_id__in=key_results.objects.values('okr_id'))
            Process_report['objective_without_keyresult'] = {'count' : len(objective_without_keyresult) , 'objective' : okrserializers(objective_without_keyresult , many=True).data}
            
            # goal with more than 5 okr 
            goal_with_too_many_objectives = goal_objs.annotate(okr_count=Count('okr')).filter(okr_count__gt=5)
            Process_report['goal_with_too_many_objectives'] = {'count' : len(goal_with_too_many_objectives) , 'goals' : GoalSerializers(goal_with_too_many_objectives , many=True).data}
            
            # goal with more than 5 okr 
            goal_with_too_few_objectives = goal_objs.annotate(okr_count=Count('okr')).filter(okr_count=1)
            Process_report['goal_with_too_few_objectives'] = {'count' : len(goal_with_too_few_objectives) , 'goals' : GoalSerializers(goal_with_too_few_objectives , many=True).data}
            
            return Response(Process_report,status=status.HTTP_200_OK)
        
        # getting all creating reports
        if company_id:
            all_report = Reports.objects.filter(company_id=company_id,user_id=user_id)
            data = []
            for report in all_report:
                serializer = ReportsSerializer(report)
                report_data = serializer.data
                report_data['username'] = report.user_id.username
                report_data['profile_image'] = report.user_id.profile_image
                data.append(report_data)
            return Response(data,status=status.HTTP_200_OK)
        # getting a report inside data
        else:
            reports = Reports.objects.get(report_id=report_id)
            report_type = reports.type
            comp_id = reports.company_id
            all_report_data = ReportsSerializer(reports).data
            if report_type == 'key_results':
                key_result_data = []
                key_result = key_results.objects.filter(okr_id__goal_id__company_id=comp_id)
                serializer = key_resultsserializers(key_result,many=True)
                for key , k in zip(serializer.data , key_result):
                    key_result_dict = key
                    key_id = key.get('key_id')
                    key_result_dict['session'] = k.okr_id.session
                    key_result_data.append(key_result_dict)
                all_report_data['key_results'] = key_result_data 
      
            elif report_type == 'objectives':
                objective = okr.objects.filter(goal_id__company_id=comp_id)
                okr_serializer = okrserializers(objective,many=True)
                okr_datas = []
                for okr_data in okr_serializer.data:
                    okr_dict = okr_data
                    okr_id = okr_data.get('okr_id')
                    # for getting progress 
                    overall_gain_avg = key_results.objects.filter(okr_id=okr_id).aggregate(Avg('overall_gain'))['overall_gain__avg']
                    if overall_gain_avg is None:
                        overall_gain_avg = 0
                    else:
                        overall_gain_avg = round (overall_gain_avg)
                    okr_dict['overall_gain'] = overall_gain_avg 
                    okr_datas.append(okr_dict)
                all_report_data['okr'] = okr_datas

            elif report_type == 'goal':
                all_goals = []
                goal_objs = Goal.objects.filter(company_id=comp_id)
                for goal_obj in goal_objs:
                    goal_dict={}
                    overall_gain_goals = 0
                    serilizer=GoalSerializers(goal_obj)
                    goal_dict=serilizer.data
                    goal_id=serilizer.data.get('goal_id')
                    okr_datas=okr.objects.filter(goal_id=goal_id)
                    total_okr =len(okr_datas)
                    if okr_datas:
                        for okr_data in okr_datas:
                            okr_id = okr_data.okr_id
                            overall_gain_avg = key_results.objects.filter(okr_id=okr_id).aggregate(Avg('overall_gain'))['overall_gain__avg']
                            if overall_gain_avg is None:
                                overall_gain_avg = 0
                            else:
                                overall_gain_avg = round (overall_gain_avg)
                                overall_gain_goals += overall_gain_avg
                    try:
                        overall_gain_goals_avg = round (overall_gain_goals / total_okr)
                    except Exception:
                        overall_gain_goals_avg = 0
                    goal_dict['overall_gain'] = overall_gain_goals_avg
                    all_goals.append(goal_dict)
                all_report_data['goals'] = all_goals

            elif report_type=='teams':
                teams = team_Table.objects.filter(company_id=comp_id)
                all_teams = []
                for team in teams:
                    team_id = team.team_id
                    team_employee = team_employees.objects.filter(team_id=team_id)
                    serializer = TeamEmployeeSerializer(team_employee,many=True)
                    team_data = TeamSerializer(team).data
                    team_data['progress'] = get_avg_goalprogress_of_team(team_id)
                    team_data['Admin'] = [{"username":  user.user_id.username, **{**employee, "role": employee['role'].role_name}} for employee , user in zip(serializer.data ,team_employee ) if employee.get('role') == 'Admin']     
                    all_teams.append(team_data)
                all_report_data['teams'] = all_teams

        return Response(all_report_data,status=status.HTTP_200_OK)
    
    def delete(self,request):
        report_id=request.query_params.get('report_id')
        try:
            report_obj = Reports.objects.get(report_id=report_id)
            report_obj.delete()
            return Response({'message': 'Report deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Reports.DoesNotExist:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)


class GenerateReportView(GenericAPIView):
    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            report_type = request.data.get('report_type') 

            if not user_id:
                return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.get(user_id=user_id)
            employee_details = employee.objects.filter(user_id=user_id).first()
            role_name = employee_details.role.role_name if employee_details else "N/A"

            goals = Goal.objects.filter(goal_owners__user_id=user)
            okrs = okr.objects.filter(owners__user_id=user)

            if report_type == 'pdf':
                pdf_file, pdf_name = generate_pdf(user, role_name, goals, okrs)
                s3_url = pdf_to_s3_url(pdf_file, pdf_name)
            elif report_type == 'ppt':
                ppt_file, ppt_name = generate_ppt(user, role_name, goals, okrs)
                s3_url = pdf_to_s3_url(ppt_file, ppt_name)
            else:
                return Response({"error": "Invalid report type. Supported types are 'pdf' and 'ppt'."}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "Report generated successfully", "url": s3_url}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    