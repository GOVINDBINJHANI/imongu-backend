from imongu_backend_app.models import Goal, okr,key_results,Parents,update_key_results, team_employees
from imongu_backend_app.Serializers import key_resultsserializers,okrserializers,GoalSerializers
from imongu_backend_app.utils.owners import *
from django.db.models import Avg
from imongu_backend_app.utils.owners import *
import uuid

def save_parents(p_id,parent_type,child_type):
    parent_id = str(uuid.uuid4())
    if parent_type == 'goal':
        goal = Goal.objects.get(goal_id = p_id)
        parent_instance = Parents(parent_id = parent_id , parent_type = parent_type ,goal_id = goal , child_type = child_type)
        parent_instance.save()

    elif parent_type == 'okr':
        okr_obj = okr.objects.get(okr_id = p_id)
        parent_instance = Parents(parent_id = parent_id,parent_type = parent_type ,okr_id = okr_obj ,child_type=child_type)
        parent_instance.save()

    elif parent_type == 'key_result':
        key_obj = key_results.objects.get(key_id = p_id)
        parent_instance = Parents(parent_id =  parent_id,parent_type = parent_type ,key_id = key_obj ,child_type=child_type)
        parent_instance.save()

    return parent_id

def check_self_child_parent(p_id,current_goal_id):
    parent_goal = Goal.objects.get(goal_id=p_id)
    parent_id = parent_goal.parent_id
    if parent_id:
        parent = Parents.objects.get(parent_id=parent_id)
        if parent.goal_id == current_goal_id:
            parent.delete()
            parent_goal.parent_id = None
            parent_goal.save()        

def update_parents(p_id,parent_type,goal):
    parent_id = goal.parent_id
    if parent_id:
        parent = Parents.objects.get(parent_id=parent_id)
        parent.parent_type = parent_type
        if parent_type == 'goal':
            # here the goal which we want to assgin as parent may be possible that is child of current goal
            check_self_child_parent(p_id,goal)
            parent_goal = Goal.objects.get(goal_id = p_id)
            parent.goal_id = parent_goal
            parent.okr_id = None
            parent.key_id = None

        elif parent_type == 'okr':
            parent_goal = okr.objects.get(okr_id = p_id)
            parent.goal_id = None
            parent.okr_id = parent_goal
            parent.key_id = None

        elif parent_type == 'key_result':
            parent_goal = key_results.objects.get(key_id = p_id)
            parent.goal_id = None
            parent.okr_id = None
            parent.key_id = parent_goal
        
        parent.save()
    else:
        parent_id = save_parents(p_id,parent_type,"goal")
    return parent_id

def get_parent(parent):
    parent_details = {}
    parent_type = parent.parent_type
    if parent_type=='goal':
        parent_goal = parent.goal_id
        serilizer=GoalSerializers(parent_goal)
        goal_owners_list= goal_owner(parent_goal.goal_id)
        parent_details=serilizer.data
        company_name = parent_goal.company_id.company_name
        parent_details['company_name']=company_name
        parent_details['owners']=goal_owners_list
        okr_list,avg_okr_gain,okr_gains = get_all_okr(parent_goal.goal_id,False)
        parent_details['children']=okr_list  
        parent_details['overall_gain']=avg_okr_gain
        
    elif parent_type=='okr':
        parent_okr = parent.okr_id
        okr_data={}
        serilizers=okrserializers(parent_okr)
        okr_data=serilizers.data
        okr_id=serilizers.data.get('okr_id')    
        owners_list = okr_owner(okr_id)
        okr_data['owners']=owners_list 
        key_results_list,avg_key_gain,key_gain = get_key_result(okr_id,False)
        okr_data['key_result']=key_results_list
        okr_data['overall_gain']=avg_key_gain
        parent_details=okr_data

    elif parent_type=='key_result':
        parent_key = parent.key_id
        key_results_dict={}
        key_data_serializers=key_resultsserializers(parent_key)
        key_results_dict=key_data_serializers.data
        key_id=key_data_serializers.data.get('key_id')
        owners_list_key= key_result_owner(key_id)
        key_results_dict['owners']=owners_list_key
        parent_details = key_results_dict

    return parent_details

def update_child(id , parent_type):
    if parent_type == 'goal':
        parents = Parents.objects.filter(goal_id=id)
        if parents:
            for parent in parents:
                parent_id = parent.parent_id
                goal_obj = Goal.objects.filter(parent_id=parent_id).first()
                if goal_obj:
                    goal_obj.parent_id = None
                    goal_obj.save()
                parent.delete()

    elif parent_type == 'okr':
        parents = Parents.objects.filter(okr_id=id)
        if parents:
            for parent in parents:
                parent_id = parent.parent_id
                okr_obj = Goal.objects.filter(parent_id=parent_id).first()
                if okr_obj:
                    okr_obj.parent_id = None
                    okr_obj.save()
                parent.delete()

    elif parent_type == 'key_result':
        parents = Parents.objects.filter(key_id=id)
        if parents:
            for parent in parents:
                parent_id = parent.parent_id
                key_obj = Goal.objects.filter(parent_id=parent_id).first()
                if key_obj:
                    key_obj.parent_id = None
                    key_obj.save()
                parent.delete()

def get_child(child):
    parent_id = child.parent_id
    chiild_type = child.child_type
    all_details = {}
    if chiild_type == 'goal':
        try:
            goal = Goal.objects.get(parent_id = parent_id)
            serilizer=GoalSerializers(goal)
            goal_owners_list= goal_owner(goal.goal_id)
            all_details=serilizer.data
            all_details['owners']=goal_owners_list
            okr_list,avg_okr_gain ,okr_gains= get_all_okr(goal.goal_id , False)
            all_details['children']=okr_list
            all_details['overall_gain']=avg_okr_gain
        except Goal.DoesNotExist:
            child.delete()
    return all_details

def get_key_result(okr_id,check_child):
    key_results_list= []
    key_gain = 0
    key_results_data=key_results.objects.filter(okr_id=okr_id)
    if key_results_data:
        for results_data in key_results_data:
            key_results_dict={}
            key_data_serializers=key_resultsserializers(results_data)
            key_results_dict=key_data_serializers.data
            key_id=key_data_serializers.data.get('key_id')
            owners_list_key= key_result_owner(key_id)
            key_results_dict['owners']=owners_list_key
            key_results_dict['child_type'] = 'key_result'
            key_gain += key_data_serializers.data.get('overall_gain')
            # checking their child
            if check_child:           
                try:
                    child = Parents.objects.get(key_id=key_id)
                    child_goal = get_child(child)
                    child_goal['parent_type'] = 'key_result'
                    child_goal_gain = child_goal['overall_gain']
                    key_results_dict['children'] = child_goal
                except Parents.DoesNotExist :
                    pass

            key_results_list.append(key_results_dict)
    try:
        n = len(key_results_data)   
        avg_key_gain = round (key_gain / n)
    except Exception:
        avg_key_gain = 0
    return key_results_list,avg_key_gain,key_gain

def get_all_okr(goal_id,check_child):
    okrs=okr.objects.filter(goal_id=goal_id)
    okr_list=[]
    overall_gain_goals = 0
    if okrs:          
        for data in okrs:
            okr_data={}
            serilizers=okrserializers(data)
            okr_data=serilizers.data
            okr_id=serilizers.data.get('okr_id')    
            owners_list = okr_owner(okr_id)
            okr_data['owners']=owners_list 
            okr_data['child_type'] = 'objective'
            key_results_list,avg_key_gain,key_gain = get_key_result(okr_id,check_child)
            # checking their child
            if check_child:
                try:
                    child = Parents.objects.get(okr_id=okr_id)
                    child_goal = get_child(child)
                    child_goal['parent_type'] = 'okr'
                    child_goal_gain = child_goal['overall_gain']
                    key_results_list.append(child_goal)
                    try:
                        n = len(key_results_list)   
                        avg_key_gain = round ((key_gain+child_goal_gain) / n)
                    except Exception:
                        avg_key_gain = 0
                except Parents.DoesNotExist :
                    pass
            okr_data['children']=key_results_list
            okr_data['overall_gain']=avg_key_gain
            overall_gain_goals += avg_key_gain 
            okr_list.append(okr_data)
    try:
        n = len(okrs)   
        avg_okr_gain = round (overall_gain_goals / n)
    except Exception:
        avg_okr_gain = 0

    return okr_list,avg_okr_gain,overall_gain_goals

# getting goal progress 
def get_goal_progress(filtered_okr):
    overall_gain_okr = 0;okr_progress=0
    if filtered_okr:
        n = len(filtered_okr)
        for okrs in filtered_okr:
            okr_id = okrs.okr_id
            okr_gain = key_results.objects.filter(okr_id=okr_id).aggregate(Avg('overall_gain'))['overall_gain__avg']
            if okr_gain is None:
                gain_avg = 0
            else:
                gain_avg = round (okr_gain)
                overall_gain_okr += gain_avg
        okr_progress = round(overall_gain_okr / n )

    return okr_progress

def get_avg_goalprogress_of_team(team_id):
    avg_goal_progress = 0
    # getting goal progress 
    overall_gain_goal = 0
    filtered_gaol = Goal.objects.filter(goal_owners__team_id = team_id)
    if filtered_gaol:
        n = len(filtered_gaol)
        for goal in filtered_gaol:
            goal_id = goal.goal_id
            filtered_okrs = okr.objects.filter(goal_id=goal_id)
            goal_gain = get_goal_progress(filtered_okrs)
            overall_gain_goal += goal_gain

        avg_goal_progress = round(overall_gain_goal / n)

    return avg_goal_progress

def get_okr_progress(okr_id):
    gain_avg = 0
    okr_gain = key_results.objects.filter(okr_id=okr_id).aggregate(Avg('overall_gain'))['overall_gain__avg']
    if okr_gain is None:
        gain_avg = 0
    else:
        gain_avg = round (okr_gain)
    return gain_avg

# updating calculation while intial value and target value is changed 
def update_base_calculation(key_id):
    key_obj = key_results.objects.get(key_id = key_id)
    updated_key_results = update_key_results.objects.filter(key_id=key_id)
    initial_number = key_obj.initial_number
    target_number  = key_obj.target_number
    for updated_key_result in updated_key_results:
        new_number = updated_key_result.new_number
        if target_number == initial_number:
            gain = 0     
        else:
            gain= round((new_number-initial_number)/(target_number-initial_number)*100)
        updated_key_result.gain =gain
        updated_key_result.save()
    
    overall_gain = 0
    if updated_key_results:
        overall_gain = updated_key_results.latest('changed_at').gain
        key_obj.overall_gain = overall_gain
        key_obj.save()
    return overall_gain

def check_owner_in_data(data,user_id):
    if user_id:
        # Check if the user_id exists in the goal_owners list
        data_owners = data.get("owners", [])
        user_in_okr_owners = False
        if len(data_owners) > 1:
            user_in_okr_owners = any( owner["id"] == user_id for owner in data_owners)
            
        if not user_in_okr_owners:
            for owner in data_owners:
                team_id = owner["id"]
                if team_id:
                    team_employee_exists = team_employees.objects.filter(
                        team_id=team_id, user_id=user_id
                    ).exists()
                    if team_employee_exists:
                        user_in_okr_owners = True
                        break
        if not user_in_okr_owners:
            return False

    return True
    

def check_shared_key_results(left_okr, user_id):
    overall_gain_okrs = 0
    all_okr = []
    okr_serializer = okrserializers(left_okr, many=True)
    okr_serializers_data = okr_serializer.data
    for okr in okr_serializers_data:
        okr_dict = okr
        all_key_results = okr_dict.get('children')
        filter_key_results = [ key_result for key_result in all_key_results if check_owner_in_data(key_result,user_id)]
        if filter_key_results:
            okr_dict['children'] = filter_key_results
            overall_gain_avg = sum(d['overall_gain'] for d in filter_key_results) / len(filter_key_results) if filter_key_results else 0
            if overall_gain_avg is None:
                overall_gain_avg = 0
            else:
                overall_gain_avg = round (overall_gain_avg)
                overall_gain_okrs += overall_gain_avg
                                
            okr_dict['overall_gain']=overall_gain_avg
            all_okr.append(okr_dict)
        
    return all_okr, overall_gain_okrs

def check_shared_okr(left_goal, user_id):
    all_goals = []
    goal_objs_data = GoalSerializers(left_goal, many=True) 
    for goal_obj in goal_objs_data.data:
        goal_dict=goal_obj
        overall_gain_goals = 0
        goal_id=goal_obj.get('goal_id')
        okr_instances = okr.objects.filter(goal_id=goal_id).prefetch_related( "owners")
        okr_list=[]
        if okr_instances:
            okr_serializer = okrserializers(okr_instances, many=True, context={'user_id': int(user_id), "shared" : False})
            valid_okrs = [data for data in okr_serializer.data if data is not None]
            for okr_data in valid_okrs:
                okr_dict= okr_data
                all_key_results=okr_data.get('children')
                overall_gain_avg = sum(d['overall_gain'] for d in all_key_results) / len(all_key_results) if all_key_results else 0
                if overall_gain_avg is None:
                    overall_gain_avg = 0
                else:
                    overall_gain_avg = round (overall_gain_avg)
                    overall_gain_goals += overall_gain_avg
                okr_dict['overall_gain']=overall_gain_avg
                okr_list.append(okr_dict)

            goal_dict['children']=okr_list
            try:
                n = len(okr_instances)
                overall_gain_goals_avg = round (overall_gain_goals / n)
            except Exception:
                overall_gain_goals_avg = 0
            goal_dict['overall_gain'] = overall_gain_goals_avg
            if valid_okrs:
                all_goals.append(goal_dict)
        
    return all_goals

def get_list_of_okr(goal_id):
    okrs=okr.objects.filter(goal_id=goal_id)
    okr_list=[]
    overall_gain_goals = 0
    serilizers=okrserializers(okrs, many=True)
    all_okr_data = serilizers.data
    if okrs:          
        for data in all_okr_data:
            okr_data=data
            okr_id=okr_data.get('okr_id')  
            all_key_results=okr_data.get('children')
            avg_key_gain = sum(d['overall_gain'] for d in all_key_results) / len(all_key_results) if all_key_results else 0
            if avg_key_gain is None:
                avg_key_gain = 0
            else:
                avg_key_gain = round (avg_key_gain)
            okr_data['overall_gain']=avg_key_gain
            overall_gain_goals += avg_key_gain 
            okr_list.append(okr_data)
    try:
        n = len(okrs)   
        avg_okr_gain = round (overall_gain_goals / n)
    except Exception:
        avg_okr_gain = 0

    return okr_list,avg_okr_gain,overall_gain_goals