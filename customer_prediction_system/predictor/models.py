from django.conf import settings
from django.db import models


class Customer(models.Model):
    customer_id = models.CharField(max_length=100, unique=True, primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.customer_id})"


class UserProfile(models.Model):
    """Links a Django user to a Customer for scoped API access."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='user_profiles',
    )

    @classmethod
    def get_or_create_for_user(cls, user, customer):
        """
        Safe get_or_create: the FK must appear in ``defaults`` when the lookup
        is only ``user``, or inserts will leave ``customer_id`` null and fail.

        Returns ``(profile, created)`` like ``QuerySet.get_or_create``.
        """
        return cls.objects.get_or_create(
            user=user,
            defaults={'customer': customer},
        )

    def __str__(self):
        return f"{self.user.get_username()} → {self.customer.customer_id}"


class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('Debit', 'Debit'),
        ('Credit', 'Credit'),
    ]

    transaction_id = models.CharField(max_length=100, unique=True, primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='transactions')
    transaction_datetime = models.DateTimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    vendor = models.CharField(max_length=200)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    next_transaction_date = models.DateTimeField(null=True, blank=True)
    likelihood_prediction = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_datetime']

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.customer} - ${self.amount}"
