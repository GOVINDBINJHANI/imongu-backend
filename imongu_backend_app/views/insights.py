from rest_framework import status
from imongu_backend_app.models import Goal, okr,key_results,team_Table
from  imongu_backend_app.Serializers import GoalSerializers, okrserializers,key_resultsserializers,TeamSerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.db.models import Avg
from imongu_backend_app.utils.owners import *
from imongu_backend_app.utils.helper import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId


class insights(GenericAPIView):
    permission_classes = [IsValidUser]

    def get(self,request):
        company_id=request.query_params.get('company_id')
        goal_objs=Goal.objects.filter(company_id=company_id)
        totalgoal = 0 ; totalokr = 0; totalkeyresult = 0
        goal_progress = {
            "0-30" : 0 ,
            "30-50" : 0 ,
            "50-70" : 0 ,
            "above-70" : 0
        } 
        okr_progress = {
           "0-30" : 0 ,
            "30-50" : 0 ,
            "50-70" : 0 ,
            "above-70" : 0
        } 
        key_progress = {
            "0-30" : 0 ,
            "30-50" : 0 ,
            "50-70" : 0 ,
            "above-70" : 0
        } 
        all_goal_data = [] ; all_okr_data = [] ; key_result_data = []
        if goal_objs:
            goal_objs_data = GoalSerializers(goal_objs, many=True).data
            for goal_data in goal_objs_data:
                overall_gain_goals = 0
                # goal_data = GoalSerializers(goal_obj).data
                goal_id = goal_data.get('goal_id')
                okr_datas = okr.objects.filter(goal_id=goal_id)
                
                if okr_datas:
                    okr_serializer_data = okrserializers(okr_datas, many=True).data
                    for okr_data in okr_serializer_data:
                        key_result = okr_data.get('children')
                        overall_gain_avg = 0
                        if key_result:
                            for key_data in key_result:
                                gain  = key_data.get('overall_gain')
                                key_id = key_data.get('key_id')
                                overall_gain_avg +=gain
                                progress_key = self.calculate_progress_key(gain)
                                key_progress[progress_key] += 1
                                totalkeyresult += 1
                                key_result_data.append(key_data)
                            try:
                                n = len(key_result)
                                overall_gain_avg = round (overall_gain_avg / n)
                                overall_gain_goals += overall_gain_avg
                            except Exception:
                                overall_gain_avg = 0
                        okr_data['overall_gain'] = overall_gain_avg
                        progress_key = self.calculate_progress_key(overall_gain_avg)
                        okr_progress[progress_key] += 1
                        totalokr += 1
                        all_okr_data.append(okr_data)
                try:
                    n = len(okr_datas)
                    goals_avg = round (overall_gain_goals / n)
                except Exception:
                    goals_avg = 0
                progress_key = self.calculate_progress_key(goals_avg)
                goal_progress[progress_key] += 1
                totalgoal += 1
                goal_data['overall_gain'] = goals_avg
                all_goal_data.append(goal_data)

        progress_distribution = {
            'goals' : all_goal_data,
            'okrs' : all_okr_data,
            'key_results' : key_result_data,
            'goal_progress': [{"name": key, "count": value} for key, value in goal_progress.items()],
            'okr_progress': [{"name": key, "count": value} for key, value in okr_progress.items()],
            'key_progress': [{"name": key, "count": value} for key, value in key_progress.items()],
            'totalgoal' : totalgoal ,
            'totalokr' : totalokr ,
            'totalkeyresult' : totalkeyresult,
        }
 
        return Response(progress_distribution ,status=status.HTTP_200_OK)
    
    def calculate_progress_key(self, value):
        if value <= 30:
            return "0-30"
        elif value <= 50:
            return "30-50"
        elif value <= 70:
            return "50-70"
        else:
            return "above-70"

class stategicReport(GenericAPIView):
    permission_classes = [IsValidUser]
    
    def get(self,request):
        company_id=request.query_params.get('company_id')
        key_result =key_results.objects.filter(okr_id__goal_id__company_id = company_id)
        overall_gain_avg = key_result.aggregate(Avg('overall_gain'))['overall_gain__avg']
        if overall_gain_avg is None:
            overall_gain_avg = 0
        else:
            overall_gain_avg = round (overall_gain_avg)
        count = len(key_result)
        Average_Progress = {}
        # get all teams with this company id
        teams = team_Table.objects.filter(company_id=company_id)
        team_count = 0
        all_teams = []
        if teams:
            team_count = len(teams)
            for team in teams:
                key_progress = 0 ; okr_progress = 0 ; goal_progress = 0
                team_dict = {}
                serializer = TeamSerializer(team) 
                team_id = team.team_id
                # getting key result progress 
                filtered_key_results = key_results.objects.filter(result_owner__team_id=team_id)
                key_serialzer = key_resultsserializers(filtered_key_results,many=True).data
                average_overall_gain = filtered_key_results.aggregate(Avg('overall_gain'))['overall_gain__avg']
                if average_overall_gain:
                    key_progress = average_overall_gain

                # getting okr progress 
                filtered_okr = okr.objects.filter(owners__team_id = team_id)
                okr_serialzer = okrserializers(filtered_okr,many=True).data
                okr_progress = get_goal_progress(filtered_okr)

                # getting goal progress 
                overall_gain_goal = 0
                filtered_gaol = Goal.objects.filter(goal_owners__team_id = team_id)
                goal_serialzer = GoalSerializers(filtered_gaol,many=True).data
                if filtered_gaol:
                    n = len(filtered_gaol)
                    for goal in filtered_gaol:
                        goal_id = goal.goal_id
                        filtered_okrs = okr.objects.filter(goal_id=goal_id)
                        goal_gain = get_goal_progress(filtered_okrs)
                        overall_gain_goal += goal_gain

                    goal_progress = round(overall_gain_goal / n)        
                team_dict = serializer.data
                team_dict['key_progress'] = key_progress
                team_dict['okr_progress'] = okr_progress
                team_dict['goal_progress'] = goal_progress
                team_dict['goals'] = goal_serialzer
                team_dict['okrs'] = okr_serialzer
                team_dict['key_results'] = key_serialzer
                all_teams.append(team_dict)
                
        Average_Progress['teams'] = all_teams     
        Average_Progress['team_count'] = team_count
        Average_Progress['total_key_result'] = count
        Average_Progress['overall_gain_avg'] = overall_gain_avg
        average_confidence = "ON TRACK" if overall_gain_avg > 60 else "AT HIGH RISK"
        Average_Progress['average_confidence'] = average_confidence
        
        return Response(Average_Progress ,status=status.HTTP_200_OK)
