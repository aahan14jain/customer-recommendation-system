from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Customer, Transaction
from .serializers import CustomerSerializer, TransactionSerializer, TransactionListSerializer


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve customers."""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    lookup_field = 'customer_id'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'customer_id']
    ordering_fields = ['last_name', 'first_name', 'created_at']

    @action(detail=True, methods=['get'])
    def transactions(self, request, customer_id=None):
        """Get all transactions for a customer."""
        customer = self.get_object()
        transactions = customer.transactions.all()[:100]  # Limit for performance
        serializer = TransactionListSerializer(transactions, many=True)
        return Response(serializer.data)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve transactions."""
    queryset = Transaction.objects.select_related('customer').all()
    serializer_class = TransactionSerializer
    lookup_field = 'transaction_id'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['transaction_id', 'vendor', 'customer__first_name', 'customer__last_name']
    ordering_fields = ['transaction_datetime', 'amount', 'likelihood_prediction']
