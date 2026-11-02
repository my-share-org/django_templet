from rest_framework.pagination import PageNumberPagination

from apps.core.utils.response import success_response


class StandardPagination(PageNumberPagination):
    page_size              = 50
    page_size_query_param  = "page_size"
    max_page_size          = 1000

    def get_paginated_response(self, data, message="Results retrieved"):
        return success_response(
            message=message,
            data={
                "count":    self.page.paginator.count,
                "next":     self.get_next_link(),
                "previous": self.get_previous_link(),
                "results":  data,
            },
        )
