import logging

from rest_framework import permissions, viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Customer, Transaction, UserProfile
from .pipeline import get_recommendations_for_customer
from .serializers import CustomerSerializer, TransactionSerializer, TransactionListSerializer

logger = logging.getLogger(__name__)


def _customer_id_for_user(user):
    """Return linked Customer.customer_id, or None if missing / anonymous."""
    if not user.is_authenticated:
        return None
    try:
        return user.profile.customer.customer_id
    except UserProfile.DoesNotExist:
        return None


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve customers."""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    lookup_field = 'customer_id'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'customer_id']
    ordering_fields = ['last_name', 'first_name', 'created_at']

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def transactions(self, request, customer_id=None):
        """Get transactions for the authenticated user's linked customer only."""
        scoped_id = _customer_id_for_user(request.user)
        if scoped_id is None:
            return Response(
                {'detail': 'No customer profile linked to this account.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if customer_id != scoped_id:
            return Response(
                {'detail': 'You may only access your own transactions.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        customer = self.get_object()
        transactions = customer.transactions.all()[:100]  # Limit for performance
        serializer = TransactionListSerializer(transactions, many=True)
        return Response(serializer.data)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve transactions for the logged-in user's linked customer only."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransactionSerializer
    lookup_field = 'transaction_id'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['transaction_id', 'vendor', 'customer__first_name', 'customer__last_name']
    ordering_fields = ['transaction_datetime', 'amount', 'likelihood_prediction']

    def get_queryset(self):
        qs = Transaction.objects.select_related('customer').all()
        customer_id = _customer_id_for_user(self.request.user)
        if customer_id is None:
            return Transaction.objects.none()
        return qs.filter(customer__customer_id=customer_id)


class RecommendationsMeView(APIView):
    """
    Personalized recommendations for the authenticated user only.
    Customer scope comes from UserProfile; customer_id is never taken from the request.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        customer_id = _customer_id_for_user(request.user)
        if customer_id is None:
            return Response(
                {
                    'detail': (
                        'No customer profile linked to this account. '
                        'An administrator must link your user to a customer record.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response(
                {'detail': 'Linked customer record was not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        txn_qs = Transaction.objects.filter(customer__customer_id=customer_id)
        if not txn_qs.exists():
            return Response(
                {
                    'customer': CustomerSerializer(customer).data,
                    'transaction_count': 0,
                    'recommendations': [],
                    'detail': 'No transactions on file for this account.',
                },
                status=status.HTTP_200_OK,
            )

        try:
            payload = get_recommendations_for_customer(customer_id, top_n=5)
        except Exception:
            logger.exception(
                'Recommendations pipeline failed for customer_id=%s', customer_id
            )
            return Response(
                {
                    'detail': (
                        'Recommendations are temporarily unavailable. '
                        'Please try again later.'
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                'customer': CustomerSerializer(customer).data,
                'transaction_count': txn_qs.count(),
                **payload,
            },
            status=status.HTTP_200_OK,
        )
