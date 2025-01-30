from rest_framework import status
from imongu_backend_app.models import Goal, okr
from imongu_backend_app.Serializers import GoalSerializers, okrserializers
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.db.models import Avg
from imongu_backend_app.utils.owners import *
from imongu_backend_app.utils.helper import *
from imongu_backend_app.utils.notification import *
from imongu_backend_app.utils.jira import *
from rest_framework.exceptions import ValidationError
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId


class sharedOkr(GenericAPIView):
    permission_classes = [IsValidUser]

    def get(self,request):
        all_goals=[]
        company_id=request.query_params.get('company_id')
        user_id = GetUserId.get_user_id(request)
        session = request.query_params.get('session')

        # Validate required parameters
        if not company_id or not user_id:
            return Response({"error": "company_id and user_id are required parameters."},
                            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user_id = int(user_id)
            queryset=Goal.objects.filter(company_id=company_id).prefetch_related( "goal_owners").order_by('-created_at')
            
            if session:
                goal_objs=queryset.filter(session=session)
            else:
                goal_objs=queryset

            
            if goal_objs:
                goal_objs_data = GoalSerializers(goal_objs, many=True).data
                for goal_obj in goal_objs_data:
                    goal_dict=goal_obj
                    overall_gain_goals = 0
                    goal_id=goal_obj.get('goal_id')
                    okr_instances = okr.objects.filter(goal_id=goal_id).prefetch_related("owners")
                    okr_list=[]
                    if okr_instances:
                        okr_serializer = okrserializers(okr_instances, many=True, context={'user_id': user_id, "shared" : True})
                        okr_serializers_data = okr_serializer.data
                        okr_ids_in_data = [okr['okr_id'] for okr in okr_serializers_data if okr is not None]
                        left_okr = okr_instances.exclude(okr_id__in=okr_ids_in_data)

                        # check if current user present in key result owner then add it to shared okr
                        all_okr, overall_gain_okrs = check_shared_key_results(left_okr, user_id)
                        overall_gain_goals += overall_gain_okrs
                        okr_list.extend(all_okr)
                        valid_okrs = [okr_data for okr_data in okr_serializers_data if okr_data is not None]
                        # check if current user present in objective owner then add it to shared okr
                        for okr_data in valid_okrs:
                            okr_dict= okr_data
                            all_key_results = okr_dict.get('children')
                            overall_gain_avg = sum(d['overall_gain'] for d in all_key_results) / len(all_key_results) if all_key_results else 0
                            # overall_gain_avg =key_result_instance.aggregate(Avg('overall_gain'))['overall_gain__avg']
                            if overall_gain_avg is None:
                                overall_gain_avg = 0
                            else:
                                overall_gain_avg = round (overall_gain_avg)
                                overall_gain_goals += overall_gain_avg
                            okr_dict['overall_gain']=overall_gain_avg
                            okr_list.append(okr_dict)
                    
                    if okr_list:
                        goal_dict['children']=okr_list
                        try:
                            n = len(okr_instances)
                            overall_gain_goals_avg = round (overall_gain_goals / n)
                        except Exception:
                            overall_gain_goals_avg = 0
                        goal_dict['overall_gain'] = overall_gain_goals_avg

                        all_goals.append(goal_dict)

            return Response(all_goals , status=status.HTTP_200_OK)
        
        except Goal.DoesNotExist:
            return Response({"error": "Goals not found for the provided company_id."}, status=status.HTTP_404_NOT_FOUND)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
