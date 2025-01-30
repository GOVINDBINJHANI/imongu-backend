from imongu_backend_app.models import User, employee, Role
from .models import Subscription
from payment.serializer import SubscriptionSerializer
from django.conf import settings
import stripe
from django.utils import timezone
import datetime


def create_stripe_customer(user_id):
    user = User.objects.get(user_id=user_id)
    customers = stripe.Customer.list(email=user.email).data
    if customers:
        return customers[0]

    else:
        stripe_customer = stripe.Customer.create(name=user.username, email=user.email)
        return stripe_customer


def create_free_trial_subscription(user_id, Company):
    free_trial_price_id = settings.TRIAL_PRICE_ID
    priduct_id = settings.STRIPE_PRODUCT_ID
    stripe_customer = create_stripe_customer(user_id)
    subscription = stripe.Subscription.create(
        customer=stripe_customer.id,
        items=[{"price": free_trial_price_id}],
        trial_period_days=14,
    )
    subscription_table = Subscription(
        user_id=User.objects.get(user_id=user_id),
        plan_name="Expanded",
        stripe_price_id=free_trial_price_id,
        subscription_stripe_id=subscription.id,
        customer_stripe_id=stripe_customer.id,
        stripe_product_id=priduct_id,
        status=subscription.status,
        current_period_start=datetime.datetime.fromtimestamp(
            subscription.current_period_start
        ),
        current_period_end=datetime.datetime.fromtimestamp(
            subscription.current_period_end
        ),
        amount=0,
        company_id=Company,
    )
    subscription_table.save()


def get_plan_data(user_id):
    user_subscription = Subscription.objects.get(user_id=user_id)
    serializer = SubscriptionSerializer(user_subscription)
    data = serializer.data
    if user_subscription.current_period_start and user_subscription.current_period_end:
        remaining_days = max(
            (user_subscription.current_period_end - timezone.now()).days + 1, 0
        )
        data["remaining_days"] = remaining_days
    else:
        data["remaining_days"] = 0
    return data


def add_user_to_stripe(company_id):
    role_id = Role.objects.get(role_name="Admin")
    # user_id = employee.objects.get(company_id=company_id, role=role_id).user_id.user_id

    user_subscription = Subscription.objects.get(company_id=company_id)
    subscription = stripe.Subscription.retrieve(
        user_subscription.subscription_stripe_id
    )

    plan_name = user_subscription.plan_name

    # Find the subscription item with the specific price ID
    subscription_item_id = None
    for item in subscription["items"]["data"]:
        if plan_name == "Expanded" or plan_name == "Basic":
            subscription_item_id = item["id"]
            current_quantity = item.get("quantity", 1)
            break

    print("subscription item id", subscription_item_id)
    print("stripe sub id", user_subscription.subscription_stripe_id)

    if subscription_item_id:
        # Update the subscription item with the new quantity
        new_quantity = current_quantity + 1  # Incrementing by 1 for the additional user
        updated_subscription_item = stripe.Subscription.modify(
            user_subscription.subscription_stripe_id,
            items=[
                {
                    "id": subscription_item_id,
                    "quantity": new_quantity,
                }
            ],
            proration_behavior="always_invoice",
        )


def cancel_subscription(subscription_id):
    if subscription_id:
        stripe.Subscription.delete(subscription_id)
    else:
        print("No valid subscription ID provided.")


def get_invoice_status(invoice_id):
    invoice = stripe.Invoice.retrieve(invoice_id)
    payment_statuse = invoice["status"]
    if payment_statuse == "paid":
        return True
    return False

def delete_customer_by_stripe(email):
    customers = stripe.Customer.list(email=email).data
    if customers:
        customer = customers[0]
        stripe.Customer.delete(customer.id)
        return True
    return False