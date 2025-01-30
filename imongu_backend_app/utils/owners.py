from imongu_backend_app.models import User,goal_owners,owners,result_owner
from imongu_backend_app.Serializers import Goal_ownersSerializers,ownerserializers,result_ownerserializers

def key_result_owner(key_id):
    key_owners_data=result_owner.objects.filter(key_id=key_id)
    owners_list=[]
    key_owners_data_with_user = key_owners_data.exclude(user_id=None)
    key_owners_data_with_team = key_owners_data.exclude(team_id=None)
    if key_owners_data_with_user:
        for owners_data in key_owners_data_with_user:
            owners_dict={}
            serilizer_owner=result_ownerserializers(owners_data)
            user_id=serilizer_owner.data.get('user_id')
            user_obj = User.objects.get(user_id=user_id)
            owners_dict['type'] = "user"
            owners_dict['id']=user_id
            owners_dict['name']=user_obj.username
            owners_dict['profile_image']=user_obj.profile_image
            owners_list.append(owners_dict)
        
    if key_owners_data_with_team:
        for owners_data in key_owners_data_with_team:
            owners_dict={}
            serilizer_owner=result_ownerserializers(owners_data)
            team_id=serilizer_owner.data.get('team_id')
            owners_dict['type'] = "team"
            owners_dict['id']=team_id
            owners_dict['name']=owners_data.team_id.team_name
            owners_list.append(owners_dict)

    return owners_list

def goal_owner(goal_id):
    goalowner_objs=goal_owners.objects.filter(goal_id=goal_id)
    goalowners_data_with_user = goalowner_objs.exclude(user_id=None)
    goalowners_data_with_team = goalowner_objs.exclude(team_id=None)
    goalowner_list=[]
    if goalowners_data_with_user:
        for goalowner_obj in goalowners_data_with_user:
            goalowner_dict={}
            goal_s=Goal_ownersSerializers(goalowner_obj)
            user_id=goal_s.data.get('user_id')
            user_obj=User.objects.get(user_id=user_id)
            goalowner_dict['type'] = "user"
            goalowner_dict['id']=user_id
            goalowner_dict['name']=user_obj.username
            goalowner_dict['profile_image']=user_obj.profile_image
            goalowner_list.append(goalowner_dict)
    

    if goalowners_data_with_team:
        for goalowner_obj in goalowners_data_with_team:
            goalowner_dict={}
            goal_s=Goal_ownersSerializers(goalowner_obj)
            team_id=goal_s.data.get('team_id')
            goalowner_dict['type'] = "team"
            goalowner_dict['id']=team_id
            goalowner_dict['name']= goalowner_obj.team_id.team_name
            goalowner_list.append(goalowner_dict)

    return goalowner_list

def okr_owner(okr_id):
    owner_list=[]
    owner_data=owners.objects.filter(okr_id=okr_id)
    owner_data_with_user  = owner_data.exclude(user_id=None)
    owner_data_with_team  = owner_data.exclude(team_id=None)
    if owner_data_with_user:
        for user in owner_data_with_user:
            owner_dict={}
            owner_serilizer=ownerserializers(user)
            user_id=owner_serilizer.data.get('user_id')
            user_obj=User.objects.get(user_id=user_id)
            owner_dict['type'] = 'user'
            owner_dict['name']=user_obj.username
            owner_dict['id']=user_id
            owner_dict['profile_image'] = user_obj.profile_image
            owner_list.append(owner_dict)
    
    if owner_data_with_team:
        for user in owner_data_with_team:
            owner_dict={}
            owner_serilizer=ownerserializers(user)
            team_id=owner_serilizer.data.get('team_id')
            owner_dict['type'] = 'team'
            owner_dict['name']=user.team_id.team_name
            owner_dict['id']=team_id
            owner_list.append(owner_dict)

    return owner_list