import os
import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime, parse_date
from django.utils import timezone
from predictor.models import Customer, Transaction


class Command(BaseCommand):
    help = 'Load customer transaction data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='predictor/data/dataset.csv',
            help='Path to the CSV file to load'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        
        # Get absolute path relative to project root
        if not os.path.isabs(file_path):
            # Go up from customer_prediction_system/predictor/management/commands/
            # to customer_prediction_system/ then to parent directory
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            file_path = os.path.join(os.path.dirname(base_dir), file_path)
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Loading data from: {file_path}'))
        
        customers_created = 0
        transactions_created = 0
        customers_updated = 0
        
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Get or create customer
                customer, created = Customer.objects.get_or_create(
                    customer_id=row['customer_id'],
                    defaults={
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                    }
                )
                
                if created:
                    customers_created += 1
                else:
                    # Update customer info if it exists
                    customer.first_name = row['first_name']
                    customer.last_name = row['last_name']
                    customer.save()
                    customers_updated += 1
                
                # Parse dates - handle both date and datetime formats
                transaction_date_str = row['transaction_datetime']
                if len(transaction_date_str) == 10:  # Date format YYYY-MM-DD
                    transaction_datetime = timezone.make_aware(
                        datetime.combine(parse_date(transaction_date_str), datetime.min.time())
                    )
                else:
                    transaction_datetime = parse_datetime(transaction_date_str)
                    if transaction_datetime and timezone.is_naive(transaction_datetime):
                        transaction_datetime = timezone.make_aware(transaction_datetime)
                
                next_transaction_date = None
                if row.get('next_transaction_date'):
                    next_date_str = row['next_transaction_date']
                    if len(next_date_str) == 10:  # Date format YYYY-MM-DD
                        next_transaction_date = timezone.make_aware(
                            datetime.combine(parse_date(next_date_str), datetime.min.time())
                        )
                    else:
                        next_transaction_date = parse_datetime(next_date_str)
                        if next_transaction_date and timezone.is_naive(next_transaction_date):
                            next_transaction_date = timezone.make_aware(next_transaction_date)
                
                # Create transaction
                transaction, created = Transaction.objects.get_or_create(
                    transaction_id=row['transaction_id'],
                    defaults={
                        'customer': customer,
                        'transaction_datetime': transaction_datetime,
                        'amount': float(row['amount']),
                        'vendor': row['vendor'],
                        'transaction_type': row['transaction_type'],
                        'next_transaction_date': next_transaction_date,
                        'likelihood_prediction': float(row['likelihood_prediction']) if row.get('likelihood_prediction') else None,
                    }
                )
                
                if created:
                    transactions_created += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\nData loaded successfully!\n'
            f'Customers created: {customers_created}\n'
            f'Customers updated: {customers_updated}\n'
            f'Transactions created: {transactions_created}'
        ))

