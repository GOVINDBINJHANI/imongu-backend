from rest_framework import status
from imongu_backend_app.models import User,company, okr,key_results,update_key_results,Comments,Emoji
from imongu_backend_app.Serializers import CommentSerializer,EmojiSerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
import uuid
import datetime
from imongu_backend_app.utils.notification import *
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId


class addCoomments(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        login_user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')
        text = request.data.get('text')
        user_id = GetUserId.get_user_id(request)
        okr_id = request.data.get('okr_id','')
        key_id = request.data.get('key_id','')
        update_key_id = request.data.get('update_key_id','')
        date_created = datetime.datetime.utcnow()
        tagged_user_ids = request.data.get('tagged_user_ids', [])
        user_ids = User.objects.filter(company__company_id=company_id).values_list('user_id', flat=True)

        try:
            company_obj = company.objects.get(company_id=company_id)
            user_obj = User.objects.get(user_id=user_id)
        except company.DoesNotExist:
            return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        comment_id = str(uuid.uuid4())
        changes = {}
        changes['text'] = text
        if okr_id:
            try:
                okr_obj = okr.objects.get(okr_id=okr_id)
                comment = Comments.objects.create(comment_id=comment_id, user_id=user_obj , company_id=company_obj, text=text , date_created=date_created , okr_id=okr_obj)
                serializer = CommentSerializer(comment)
                if login_user_id:
                    user = User.objects.get(user_id=login_user_id)
                    message = user.username + " commented on an objectives"
                    changes['okr_id'] = str(okr_id)
                    save_notification(company_id, message, user, "objectives", title=okr_obj.title, changes=changes)
            except okr.DoesNotExist:
                return Response({"error": "Okr not found"}, status=status.HTTP_404_NOT_FOUND)
            
        elif key_id:
            try:
                key_obj = key_results.objects.get(key_id=key_id)
                comment = Comments.objects.create(comment_id=comment_id, user_id=user_obj , company_id=company_obj, text=text , date_created=date_created , key_id=key_obj)
                serializer = CommentSerializer(comment)
                if login_user_id:
                    user = User.objects.get(user_id=login_user_id)
                    message = user.username + " commented on a key result"
                    changes['key_id'] = str(key_id)
                    save_notification(company_id, message, user, "key result", title=key_obj.title, changes=changes)
            except key_results.DoesNotExist:
                return Response({"error": "Key results not found"}, status=status.HTTP_404_NOT_FOUND)
            
        elif update_key_id:
            try:
                update_key_obj = update_key_results.objects.get(update_key_id=update_key_id)
                key_obj = update_key_obj.key_id
                if key_obj:
                    title = key_obj.title
                else:
                    title = "No Title Available"
                comment = Comments.objects.create(comment_id=comment_id, user_id=user_obj , company_id=company_obj, text=text , date_created=date_created , update_key_id=update_key_obj)
                serializer = CommentSerializer(comment)
                if login_user_id:
                    user = User.objects.get(user_id=login_user_id)
                    message = user.username + " commented on an update key result"
                    changes['update_key_id'] = str(update_key_id)
                    save_notification(company_id, message, user, "update key results", title=title, changes=changes)
            except update_key_results.DoesNotExist:
                return Response({"error": "update key results not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self ,request):
        text = request.data.get('text')
        comment_id = request.data.get('comment_id')
        comment = Comments.objects.get(comment_id=comment_id)
        comment.text = text
        comment.save()
        return Response({"message"  : "Data update Successfully"}, status=status.HTTP_200_OK)
       
    def get(self , request):
        okr_id = request.query_params.get('okr_id','')
        key_id = request.query_params.get('key_id','')
        update_key_id = request.query_params.get('update_key_id','')
        
        if okr_id:
            comment = Comments.objects.filter(okr_id=okr_id).order_by('-date_created')
            serializer = CommentSerializer(comment,many = True)
        elif key_id:
            comment = Comments.objects.filter(key_id=key_id).order_by('-date_created')
            serializer = CommentSerializer(comment,many = True)
        elif update_key_id:
            comment = Comments.objects.filter(update_key_id=update_key_id).order_by('-date_created')
            serializer = CommentSerializer(comment,many = True)
        else:
            return Response({"Error" : "Id is not found"} , status=status.HTTP_404_NOT_FOUND)

        data = serializer.data
        data = [{ **d, 'username': com.user_id.username} for d , com in zip( data , comment)]
        return Response(data, status=status.HTTP_200_OK)
    
    def delete(self, request):
        comment_id = request.query_params.get('comment_id')
        try:
            comment = Comments.objects.get(comment_id=comment_id).delete()
            return Response({"message": "Comment deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response({"Error" : "Id is not found"} , status=status.HTTP_404_NOT_FOUND)

class addEmoji(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self,request):
        comment_id = request.data.get('comment_id')
        name = request.data.get('name')
        emoji = request.data.get('emoji')
        user_id = GetUserId.get_user_id(request)
        try:
            user_obj = User.objects.get(user_id=user_id)
            comment_obj = Comments.objects.get(comment_id=comment_id)
        except Comments.DoesNotExist:
            return Response({"error": "Comments not found"}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        emoji_id = str(uuid.uuid4())
        emoji_instance = Emoji.objects.create(id=emoji_id,name=name,emoji=emoji,comment_id=comment_obj,user_ids= [user_id])
        serializer = EmojiSerializer(emoji_instance)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self ,request):
        emoji_id = request.data.get('emoji_id')
        user_id = GetUserId.get_user_id(request)
        emoji_instance = Emoji.objects.get(id=emoji_id)
        update_user_ids = emoji_instance.user_ids
        update_user_ids.append(user_id)
        emoji_instance.user_ids = update_user_ids
        emoji_instance.save()
        return Response({"message"  : "Emoji update Successfully"}, status=status.HTTP_200_OK)
    
    def get(self , request):
        comment_id = request.query_params.get('comment_id')
        
        emojis = Emoji.objects.filter(comment_id=comment_id)
        serializer = EmojiSerializer(emojis,many = True)
        data = []
        for obj ,emoji in zip(emojis,serializer.data):
            users = obj.user_ids
            emoji['user_ids'] = [{"username":  User.objects.get(user_id=user_id).username, "user_id" : user_id} for user_id in users]
            emoji['count'] = len(users)
            data.append(emoji)

        return Response(data, status=status.HTTP_200_OK)
    
    def delete(self, request):
        emoji_id = request.query_params.get('emoji_id')
        user_id = GetUserId.get_user_id(request)
        try:
            emoji = Emoji.objects.get(id=emoji_id)
            user_ids = emoji.user_ids
            if len(user_ids) == 1:
                emoji.delete()
            else:
                user_ids.remove(user_id)
                emoji.user_ids = user_ids
                emoji.save()
            return Response({"message": "Emoji deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response({"Error" : "Id is not found"} , status=status.HTTP_404_NOT_FOUND)
