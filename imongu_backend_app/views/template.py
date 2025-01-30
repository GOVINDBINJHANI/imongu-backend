from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from imongu_backend_app.models import Template, User, Question, UserAnswer, templateUserRelation, QuestionTitle, TempComments, Schedule, company
from imongu_backend_app.Serializers import TemplateSerializer, UserAnswerSerializer, TempCommentsSerializer
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from imongu_backend_app.utils.validate_user_access import validate_user_company_access, validate_feature_activity_access

class TemplateView(APIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        # Proceed with template creation
        user_id = GetUserId.get_user_id(request)
        company_id = request.data.get('company_id')

        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        feature_name = request.resolver_match.url_name
        activity_name = "Create"
        role_id= validate_user_company_access(user_id, company_id)
        validate_feature_activity_access(role_id, company_id, feature_name, activity_name)

        serializer = TemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    


    def put(self, request):
        user_id = GetUserId.get_user_id(request)
        template_id = request.data.get('template_id')
        company_id = request.data.get('company_id')
        user = get_object_or_404(User, user_id=user_id)

        # Validate company existence
        company_id = get_object_or_404(company, company_id= company_id)
        # Validate template existence
        try:
            template = Template.objects.get(id=template_id)
        except Template.DoesNotExist:
            return Response({"error": "Template not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get default_temp status from the template
        default_temp = template.default_temp

        with transaction.atomic():
            if default_temp:
                # Create a new copy of the template
                new_template = Template.objects.create(
                    description=request.data.get('description', template.description),
                    template_title=request.data.get('template_title', template.template_title),
                    comment_text=request.data.get('comment_text',template.comment_text),
                    template_type=request.data.get('template_type', template.template_type),
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )

                # Copy existing question titles and questions to the new template
                for question_title in template.question_titles.all():
                    new_question_title = QuestionTitle.objects.create(
                        template=new_template,
                        question_title=question_title.question_title
                    )
                    for question in question_title.questions.all():
                        Question.objects.create(
                            template=new_template,
                            question_title=new_question_title,
                            text=question.text
                        )
                # Create a new templateUserRelation
                templateUserRelation.objects.create(user=user, template=new_template, company= company_id)

                # Update the new template with the provided data
                serializer = TemplateSerializer(new_template, data=request.data, partial=True)
            else:
                # Update the existing template
                serializer = TemplateSerializer(template, data=request.data, partial=True)

            if serializer.is_valid():
                updated_template = serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # New endpoint to fetch templates and questions associated with a user and default templates
    def get(self, request):
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')
        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch templates in a single query
        templates = Template.objects.filter(
            Q(templateuserrelation__user_id=user_id, templateuserrelation__company=company_id) |
            Q(default_temp=True)
        ).distinct()

        # Prepare template data including questions and question titles
        template_data = []
        for template in templates:
            serializer = TemplateSerializer(template)
            data = serializer.data
                # Try to find a relation for this template in the templateUserRelation table
            user_relation = templateUserRelation.objects.filter(template=template).first()

            if user_relation:
                # If user relation exists, fetch the user details
                user = user_relation.user
                user_data = {
                    'username': user.username,
                    'email': user.email,
                    'profile_image': user.profile_image
                }
                data['user_details'] = user_data
            else:
                # If no relation is found, set user details as None
                data['user_details'] = None
                
            question_titles = QuestionTitle.objects.filter(template=template)
            question_title_data = []
            for title in question_titles:
                questions = Question.objects.filter(question_title=title)
                question_list = [{'text': q.text} for q in questions]
                question_title_data.append({
                    'question_title': title.question_title,
                    'question_list': question_list
                })

            data['questions'] = question_title_data
            template_data.append(data)

        return Response(template_data, status=status.HTTP_200_OK)
    
    # Delete API to Delete a Template and Its Associated Questions and Question Titles
    def delete(self, request):
        user_id = GetUserId.get_user_id(request)
        template_id = request.query_params.get('template_id')
        # Validate template existence
        try:
            template = Template.objects.get(id=template_id)
        except Template.DoesNotExist:
            return Response({"error": "Template not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if the template is a default template
        if template.default_temp:
            return Response({"error": "Default templates can't be deleted."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the user has permission to delete this template
        try:
            templateUserRelation.objects.get(user_id=user_id, template_id=template_id)
        except templateUserRelation.DoesNotExist:
            return Response({"error": "You don't have permission to delete this template."}, status=status.HTTP_403_FORBIDDEN)

        # Delete the template along with all associated question titles and questions
        with transaction.atomic():
            # Delete associated templateUserRelation
            templateUserRelation.objects.filter(template_id=template_id).delete()
            
            # The deletion of QuestionTitles and Questions will be handled automatically
            # due to the CASCADE setting in the ForeignKey relationship
            template.delete()

        return Response({"message": "Template and all associated data deleted successfully."}, status=status.HTTP_204_NO_CONTENT) 

class TemplateGetView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        # Extract user_id from query parameters
        user_id = GetUserId.get_user_id(request)
        template_id = request.query_params.get('template_id')
        
        # Fetch the template
        try:
            template = Template.objects.get(id=template_id)
        except Template.DoesNotExist:
            return Response({"error": "Template not found."}, status=status.HTTP_404_NOT_FOUND)

        # Serialize the template
        serializer = TemplateSerializer(template)
        
        # Add associated question titles and questions
        template_data = serializer.data
        
        # Fetch the user details from templateUserRelation
        user_relation = templateUserRelation.objects.filter(template_id=template_id).first()

        # if not user_relation:
        #     return Response({"error": "User has not given any comment."}, status=status.HTTP_404_NOT_FOUND)
        if user_relation :
            user = user_relation.user
            # Add user details to the response
            user_data = {
                'username': user.username,
                'email': user.email,
                'profile_image': user.profile_image
            }
            template_data['user_details'] = user_data

        question_titles = QuestionTitle.objects.filter(template=template)
        question_title_data = []
        for title in question_titles:
            questions = Question.objects.filter(question_title=title)
            question_list = [{'text': q.text, 'id': q.id} for q in questions]
            question_title_data.append({
                'question_title': title.question_title,
                'question_title_id': title.id,
                'question_list': question_list
            })
        # Include question titles and questions in the response
        template_data['qa'] = question_title_data
        
        return Response(template_data)
    
class FetchTemplatesView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        # Extract user_id and company_id from query parameters
        user_id = GetUserId.get_user_id(request)
        company_id = request.query_params.get('company_id')

        
        if not company_id:
            return Response({"error": "Company ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch templates associated with the user and company or default templates
        templates = Template.objects.filter(
            Q(templateuserrelation__user_id=user_id, templateuserrelation__company=company_id) |
            Q(default_temp=True)
        ).distinct()

        # Prepare the response data
        template_data = []
        for template in templates:
            template_data.append({
                'template_id': template.id ,
                'template_title': template.template_title,
                'template_type': template.template_type
            })

        # Return the templates in the response
        return Response(template_data, status=status.HTTP_200_OK)

class UserAnswerView(APIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        user_id = request.query_params.get('user_id')
        schedule_id = request.query_params.get('schedule_id')
        if not user_id:
            return Response({"error": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not schedule_id:
            return Response({"error": "Schedule ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize filters with mandatory fields
        filters = Q(user_id=user_id, schedule_id=schedule_id)

        # Fetch UserAnswer with updated filters
        try:
            user_answer = UserAnswer.objects.get(filters)
        except UserAnswer.DoesNotExist:
            # If UserAnswer not found, fetch template using schedule_id
            try:
                # Fetch schedule to get the associated template_id
                schedule = Schedule.objects.get(id=schedule_id)
                template_id = schedule.template_id  # Assuming the Schedule model has a template_id field

                # Fetch the template details
                template = Template.objects.get(id=template_id)
                serializer = TemplateSerializer(template)
                template_data = serializer.data

                # Fetch associated question titles and questions
                question_titles = QuestionTitle.objects.filter(template=template)
                question_title_data = []
                for title in question_titles:
                    questions = Question.objects.filter(question_title=title)
                    question_list = [{'text': q.text, 'id': q.id} for q in questions]
                    question_title_data.append({
                        'question_title': title.question_title,
                        'question_title_id': title.id,
                        'question_list': question_list
                    })

                # Include question titles and questions in the response
                template_data['qa'] = question_title_data

                # Fetch user details if associated via TemplateUserRelation
                user_relation = templateUserRelation.objects.filter(template_id=template_id).first()
                if user_relation:
                    user = user_relation.user
                    user_data = {
                        'username': user.username,
                        'email': user.email,
                        'profile_image': user.profile_image
                    }
                    template_data['user_details'] = user_data
                template_data['useranswer_created'] = False

                return Response(template_data, status=status.HTTP_200_OK)

            except Schedule.DoesNotExist:
                return Response({"error": "Schedule not found for the given schedule_id."}, status=status.HTTP_404_NOT_FOUND)
            except Template.DoesNotExist:
                return Response({"error": "Template not found for the schedule's template_id."}, status=status.HTTP_404_NOT_FOUND)

        # Group answers by question_title
        grouped_answers = {}
        answers_dict = user_answer.answer

        for question_id in answers_dict:
            # Fetch the related question details
            try:
                question = Question.objects.get(id=question_id)
            except Question.DoesNotExist:
                continue  # Skip if question not found

            question_title = question.question_title.question_title
            question_text = question.text

            if question_title not in grouped_answers:
                grouped_answers[question_title] = {
                    "question_title": question_title,
                    "question_list": []
                }

            # Append question details along with the answer
            grouped_answers[question_title]["question_list"].append({
                "text": question_text,
                "id": question.id,
                "answer": answers_dict[question_id]  # Include respective answer if needed
            })

        # Convert grouped answers into a list for the response
        response_data = list(grouped_answers.values())

        # Serialize the UserAnswer details, excluding the answer field
        user_answer_data = UserAnswerSerializer(user_answer).data
        user_answer_data.pop('answer', None)  # Remove 'answer' field from the serialized data

        # Add the template description from the user answer's template
        template_description = user_answer.template.description if user_answer.template else None
        user_answer_data['template_description'] = template_description

        # Combine the answers and the serialized UserAnswer
        complete_response = {
            "user_answer": user_answer_data,
            "qa": response_data
        }
        complete_response['useranswer_created'] = True

        return Response(complete_response, status=status.HTTP_200_OK)

    def post(self, request):

        user_id = GetUserId.get_user_id(request)
        user = get_object_or_404(User, user_id=user_id)

        data = request.data.copy()
        data['user'] = user.user_id

        serializer = UserAnswerSerializer(data=data)
        if serializer.is_valid():
            validated_data = serializer.validated_data

            # user = validated_data['user']
            template = validated_data['template']
            provided_answers = validated_data.get('answer', [])

            # Convert list of answers to a dictionary
            answer_data = {ans['question_id']: ans.get('answer', "") for ans in provided_answers}

            # Retrieve all questions for the given template
            questions = Question.objects.filter(template=template)

            # Ensure all questions are included in the answers
            final_answer_data = {}
            for question in questions:
                question_id = question.id
                final_answer_data[question_id] = answer_data.get(question_id, "")

            # Update the validated_data with the processed answers
            validated_data['answer'] = final_answer_data

            # Create or update the UserAnswer instance
            user_answer = UserAnswer.objects.create(**validated_data)
            
            return Response(UserAnswerSerializer(user_answer).data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        schedule_id = request.data.get('schedule_id')
        user_id = GetUserId.get_user_id(request)
        template_id = request.data.get('template')

        if not schedule_id or not user_id or not template_id:
            return Response(
                {"error": "Schedule ID, User ID, and Template ID are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_answer = UserAnswer.objects.get(
                schedule_id=schedule_id,
                user_id=user_id,
                template_id=template_id
            )
        except UserAnswer.DoesNotExist:
            return Response(
                {"error": "No UserAnswer with the provided criteria exists."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Process the answer data to maintain the correct structure
        answer_data = request.data.get('answer', [])
        processed_answer = {str(item['question_id']): item['answer'] for item in answer_data}

        # Update the request data with the processed answer
        update_data = request.data.copy()
        update_data['answer'] = processed_answer

        serializer = UserAnswerSerializer(user_answer, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # def put(self, request):
    #     schedule_id = request.data.get('schedule_id')
    #     user_id = GetUserId.get_user_id(request)
    #     template_id = request.data.get('template')

    #     # Validating required fields
    #     if not schedule_id or not user_id or not template_id:
    #         return Response(
    #             {"error": "Schedule ID, User ID, and Template ID are required."}, 
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     # Attempting to find the UserAnswer entries with the provided criteria
    #     user_answers = UserAnswer.objects.filter(
    #         schedule_id=schedule_id,
    #         user_id=user_id,
    #         template_id=template_id
    #     )

    #     # Check if user_answers exists
    #     if not user_answers.exists():
    #         return Response(
    #             {"error": "No UserAnswer with the provided criteria exists."},
    #             status=status.HTTP_404_NOT_FOUND
    #         )

    #     # If there's only one entry, you can handle it normally
    #     if user_answers.count() == 1:
    #         user_answer = user_answers.first()
    #         serializer = UserAnswerSerializer(user_answer, data=request.data, partial=True)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return Response(serializer.data, status=status.HTTP_200_OK)
    #         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    #     # If there are multiple entries, handle them appropriately
    #     # Option 1: Update all entries with the provided data
    #     # This assumes that it's correct to apply the same update to all matching records
    #     update_data = request.data
    #     for user_answer in user_answers:
    #         serializer = UserAnswerSerializer(user_answer, data=update_data, partial=True)
    #         if serializer.is_valid():
    #             serializer.save()
    #         else:
    #             # Handle individual errors if necessary
    #             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    #     # Option 2: Return an error or handle differently if multiple records are not expected
    #     return Response(
    #         serializer.data,
    #         status=status.HTTP_200_OK
    #     )
class TempCommentsView(APIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        sender_id = request.data.get('sender_id')
        receiver_id = request.data.get('receiver_id')
        text = request.data.get('text')
        schedule_id = request.data.get('schedule_id')

        if not sender_id:
            return Response({"error": "Sender ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not receiver_id:
            return Response({"error": "Receiver ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not text:
            return Response({"error": "Text is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not schedule_id:
            return Response({"error": "Schedule ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Validate if schedule exists
            schedule = Schedule.objects.get(id=schedule_id)
        except Schedule.DoesNotExist:
            return Response({"error": "Schedule not found."}, status=status.HTTP_404_NOT_FOUND)

        # Create new TempComment
        comment_data = {
            'sender_id': sender_id,
            'receiver_id': receiver_id,
            'text': text,
            'Schedule': schedule.id
        }
        serializer = TempCommentsSerializer(data=comment_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request):
        comment_id = request.data.get('comment_id')
        new_text = request.data.get('text')

        if not comment_id:
            return Response({"error": "ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not new_text:
            return Response({"error": "New text is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the comment by ID
            comment = TempComments.objects.get(id=comment_id)
        except TempComments.DoesNotExist:
            return Response({"error": "Comment not found."}, status=status.HTTP_404_NOT_FOUND)

        # Update the comment text
        comment.text = new_text
        comment.save()

        serializer = TempCommentsSerializer(comment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get(self, request):
        sender_id = request.query_params.get('sender_id')
        receiver_id = request.query_params.get('receiver_id')
        schedule_id = request.query_params.get('schedule_id')

        if not sender_id:
            return Response({"error": "Sender ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not receiver_id:
            return Response({"error": "Receiver ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not schedule_id:
            return Response({"error": "Schedule ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Validate if schedule exists
            schedule = Schedule.objects.get(id=schedule_id)
        except Schedule.DoesNotExist:
            return Response({"error": "Schedule not found."}, status=status.HTTP_404_NOT_FOUND)

        # Fetch the comments, ordered by created_at
        comments = TempComments.objects.filter(
            Q(sender_id=sender_id, receiver_id=receiver_id) | 
            Q(sender_id=receiver_id, receiver_id=sender_id),
            Schedule=schedule
        ).order_by('created_at')

        # Fetch sender and receiver details
        sender = get_object_or_404(User, user_id=sender_id)
        receiver = get_object_or_404(User, user_id=receiver_id)

        # Serialize comments
        comments_serializer = TempCommentsSerializer(comments, many=True)
        # Prepare response data with user details
        response_data = {
            "sender_details": {
                "id": sender.user_id,
                "username": sender.username,
                "profile_image": sender.profile_image if sender.profile_image else None,
                "email": sender.email,
            },
            "receiver_details": {
                "id": receiver.user_id,
                "username": receiver.username,
                "profile_image": receiver.profile_image if receiver.profile_image else None,
                "email": receiver.email,
            },
            "comments": comments_serializer.data,
        }

        return Response(response_data, status=status.HTTP_200_OK)
    
    def delete(self, request):
        comment_id = request.query_params.get('comment_id')

        if not comment_id:
            return Response({"error": "comment ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the comment by ID
            comment = TempComments.objects.get(id=comment_id)
        except TempComments.DoesNotExist:
            return Response({"error": "Comment not found."}, status=status.HTTP_404_NOT_FOUND)

        # Delete the comment
        comment.delete()

        return Response({"message": "Comment deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
