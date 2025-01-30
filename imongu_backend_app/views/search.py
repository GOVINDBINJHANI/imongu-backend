from elasticsearch_dsl import Q
from rest_framework.pagination import LimitOffsetPagination
import abc
from imongu_backend_app.documents import GoalDocument, TeamTableDocument,OKRDocument,KeyResultsDocument,ReportDocument,EmployeeDocument
from elasticsearch_dsl import Search
from imongu_backend.settings import client
from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId


class PaginatedElasticSearchAPIView(GenericAPIView, LimitOffsetPagination):
    serializer_class = None
    document_class = None

    @abc.abstractmethod
    def generate_q_expression(self, query,company_id):
        """This method should be overridden
        and return a Q() expression."""
        raise NotImplementedError("generate_q_expression must be implemented in subclasses.")
    
    def post(self, request, query=None):
        company_id = request.data.get('company_id')
        document_type = request.data.get('document_type')
        q = self.generate_q_expression(query, company_id)
        if document_type == 'everywhere':
            # Perform the search across all indices
            search = Search(using=client, index="*").query(q) 
            response = search.execute()
            objects_list = []
            for hit in response:
                document_type = hit.meta.index  
                serializer_class = self.serializer_class_mapping.get(document_type)
                if serializer_class:
                    serializer = serializer_class(hit, many=False)  
                    data = serializer.data
                    data['document_type'] = document_type
                    objects_list.append(data)

        else:
            document_class = self.document_class_mapping.get(document_type)
            if document_class:
                search = document_class.search().query(q)
                response = search.execute()
                serializer_class= self.serializer_class_mapping[document_type]
                serializer = serializer_class(response, many=True)
                objects_list = serializer.data
            else:
                return Response({'error': 'Invalid document type'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(objects_list,status.HTTP_200_OK)

from imongu_backend_app.Serializers import GoalDocumentSerializer,OKRDocumentSerializer,KeyResultDocumentSerializer,EmployeeDocumentSerializer,TeamTableDocumentSerializer,ReportDocumentSerializer
class SearchDocuments(PaginatedElasticSearchAPIView):
    permission_classes = [IsValidUser]

    document_class_mapping = {
        'goals': GoalDocument,
        'okrs': OKRDocument,
        'key_results': KeyResultsDocument,
        'employees': EmployeeDocument,
        'teams': TeamTableDocument,
        'reports': ReportDocument
    }
    serializer_class_mapping = {
        'goals': GoalDocumentSerializer,
        'okrs': OKRDocumentSerializer,
        'key_results': KeyResultDocumentSerializer,
        'employees': EmployeeDocumentSerializer,
        'teams': TeamTableDocumentSerializer,
        'reports': ReportDocumentSerializer
    }

    def generate_q_expression(self, query,  company_id):
        searchFields = self.request.data.get('searchField',['title'])
        wildcard_queries = []

        for search_field in searchFields:
            if search_field == 'username':
                search_field = 'user_id.username'

            wildcard_query = Q("wildcard", **{search_field: f"*{query}*"}) & Q("match", company_id__company_id=company_id)
            wildcard_queries.append(wildcard_query)

        combined_query = Q("bool", should=wildcard_queries)

        return combined_query

        # if searchFields =='username':
        #     searchFields = 'user_id.username'

        #  # Construct a wildcard query to enable partial matching
        # wildcard_query = f"*{query}*"

        # return Q("wildcard", **{searchFields : wildcard_query})

        # return  Q("multi_match", 
        #           query=query, fields= searchFields, 
        #           fuzziness='auto'
        #           )
         
