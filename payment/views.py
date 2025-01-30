from rest_framework import status
from imongu_backend_app.models import User, employee, Goal, team_Table
from payment.models import Subscription
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from django.conf import settings
import stripe
from imongu_backend_app.utils.features import *
from payment.utils import *
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from imongu_backend.custom_permission.authorization import IsValidUser, GetUserId
from rest_framework.permissions import AllowAny


class StripeWebhookView(GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        sig_header = request.headers.get("Stripe-Signature")
        endpoint_secret = settings.SIGNING_SECRET_KEY
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            # Invalid payload
            return Response(
                {"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST
            )
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            return Response(
                {"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST
            )
        # Handle the event
        if event["type"] == "checkout.session.completed":
            print("checkout.session.completed")
            checkout_session = event.data.object
            user_id = checkout_session.client_reference_id
            print("checkout session ", checkout_session)
            subscription = stripe.Subscription.retrieve(checkout_session.subscription)
            print("subscription = ", subscription)
            product_name = stripe.Product.retrieve(subscription.plan.product)
            price = stripe.Price.retrieve(subscription.plan.id)
            # Get the corresponding subscription
            subscription_table = Subscription.objects.get(user_id=user_id)
            subscription_table.plan_name = product_name.name
            subscription_table.status = subscription.status
            subscription_table.amount = subscription.plan.amount
            subscription_table.stripe_product_id = subscription.plan.product
            subscription_table.stripe_price_id = subscription.plan.id
            subscription_table.customer_stripe_id = checkout_session.customer
            subscription_table.subscription_stripe_id = checkout_session.subscription
            subscription_table.current_period_start = datetime.fromtimestamp(
                subscription.current_period_start
            )
            subscription_table.current_period_end = datetime.fromtimestamp(
                subscription.current_period_end
            )
            if subscription.status == "active":
                subscription_table.free_trial_status = False
            subscription_table.save()

        elif event["type"] == "customer.subscription.updated":
            print("customer.subscription.updated")
            update_subscription = event.data.object
            print("update_subscription", update_subscription)
            latest_invoice = update_subscription["latest_invoice"]
            plan_id = update_subscription["plan"]["id"]
            stripe_customer = stripe.Customer.retrieve(update_subscription.customer)
            subscription = stripe.Subscription.retrieve(update_subscription.id)
            product_name = stripe.Product.retrieve(subscription.plan.product)
            subscription_table = Subscription.objects.get(
                user_id__email=stripe_customer.email
            )
            invoice_status = get_invoice_status(latest_invoice)
            if invoice_status:
                subscription_table.plan_name = product_name.name
                subscription_table.status = subscription.status
                subscription_table.amount = subscription.plan.amount
                subscription_table.stripe_product_id = subscription.plan.product
                subscription_table.stripe_price_id = subscription.plan.id
                subscription_table.customer_stripe_id = update_subscription.customer
                subscription_table.subscription_stripe_id = update_subscription.id
                subscription_table.current_period_start = datetime.fromtimestamp(
                    subscription.current_period_start
                )
                subscription_table.current_period_end = datetime.fromtimestamp(
                    subscription.current_period_end
                )
                if subscription.status == "active":
                    subscription_table.free_trial_status = False
                subscription_table.save()

        elif event.type == "customer.subscription.deleted":
            print("customer.subscription.deleted")
            subscription = event.data.object
            print(" delete subscription ", subscription)
            subscription_table = Subscription.objects.get(
                subscription_stripe_id=subscription.id
            )
            user_id = subscription_table.user_id
            subscription_table.status = subscription.status
            subscription_table.plan_name = "Free"
            subscription_table.free_trial_status = False
            subscription_table.save()

        elif event.type == "payment_intent.succeeded":
            print("payment_intent.succeeded")
            payment_intent = event.data.object

        elif event.type == "invoice.payment_failed":
            print("invoice.payment_failed")
            payment_intent = event.data.object
            subscription_table = Subscription.objects.get(
                user_id__email=payment_intent.customer_email
            )
            subscription_table.status = "canceled"
            subscription_table.plan_name = "Free"
            subscription_table.amount = 0
            subscription_table.free_trial_status = False
            subscription_table.save()
            cancel_subscription(subscription_table.subscription_stripe_id)

        else:
            pass

        return Response({"status": "success"}, status=status.HTTP_200_OK)


class CustomerPortal(GenericAPIView):
    permission_classes = [IsValidUser]

    def post(self, request):
        user_id = GetUserId.get_user_id(request)
        price_id = request.data.get("price_id")

        try:
            # Fetch subscription for the user
            subscription = Subscription.objects.get(user_id=user_id)
        except ObjectDoesNotExist:
            return Response(
                {"error": "Subscription not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        customer_id = subscription.customer_stripe_id

        try:
            if subscription.status == "canceled":
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    customer=customer_id,
                    line_items=[
                        {
                            "price": price_id,
                            "quantity": 1,
                        }
                    ],
                    mode="subscription",
                    success_url=settings.SUCCESS_URL,
                    cancel_url=settings.CANCEL_URL,
                )
            else:
                session = stripe.billing_portal.Session.create(
                    customer=customer_id,
                    return_url=settings.RETURN_URL,
                )

            return Response({"url": session.url}, status=status.HTTP_200_OK)

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SubscriptionView(GenericAPIView):
    permission_classes = [IsValidUser]

    def get(self, request):
        company_id = request.query_params.get("company_id")
        super_admin_role = Role.objects.filter(role_name="Admin").values("id").first()

        # Use filter to handle multiple admins
        super_admins = employee.objects.filter(
            company_id=company_id, role=super_admin_role["id"]
        )

        if super_admins.exists():
            # Assuming you want the first admin if there are multiple
            user_id = super_admins.first().user_id.user_id
            user = User.objects.get(user_id=user_id)
        else:
            return Response(
                {"error": "No admin found"}, status=status.HTTP_404_NOT_FOUND
            )

        data = get_plan_data(user_id)
        plan_name = data["plan_name"]
        features = {}

        if plan_name == "Free":
            features = free
        elif plan_name == "Basic":
            features = basic_plan
        elif plan_name == "Expanded":
            features = expandend
        elif plan_name == "Premium":
            features = premium
        else:
            features = {}
        team_member_limit = features.get("team_member", 0)
        if team_member_limit > 0:
            current_team_count = (
                employee.objects.filter(company_id=company_id)
                .exclude(role=super_admin_role["id"])
                .count()
            )
            remaining_team_members = max(0, team_member_limit - current_team_count)
        else:
            remaining_team_members = 0

        goal_count = Goal.objects.filter(company_id=company_id).count()
        team_count = team_Table.objects.filter(company_id=company_id).count()
        data["goal_count"] = goal_count
        data["team_count"] = team_count
        data["features"] = features
        data["email"] = user.email
        data["username"] = user.username
        data["employees_count"] = (
            employee.objects.filter(company_id=company_id)
            .exclude(role=super_admin_role["id"])
            .count()
        )
        data["remaining_team_members"] = remaining_team_members
        return Response(data, status=status.HTTP_200_OK)
