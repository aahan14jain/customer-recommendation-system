from rest_framework import serializers
from .models import Customer, Transaction


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['customer_id', 'first_name', 'last_name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Transaction
        fields = [
            'transaction_id',
            'customer',
            'customer_id',
            'transaction_datetime',
            'amount',
            'vendor',
            'transaction_type',
            'next_transaction_date',
            'likelihood_prediction',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def create(self, validated_data):
        customer_id = validated_data.pop('customer_id', None)
        if customer_id:
            customer = Customer.objects.get(customer_id=customer_id)
            validated_data['customer'] = customer
        return super().create(validated_data)


class TransactionListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing transactions"""
    customer_name = serializers.CharField(source='customer.__str__', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'transaction_id',
            'customer_name',
            'amount',
            'vendor',
            'transaction_type',
            'transaction_datetime',
            'likelihood_prediction'
        ]


