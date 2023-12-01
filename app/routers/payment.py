from fastapi import FastAPI, HTTPException, APIRouter
from fastapi import Depends, HTTPException
import stripe
from dotenv import load_dotenv
import os


router = APIRouter(
    prefix="/payments",
    tags=["Pyaments"],
    )
load_dotenv()
# Configure Stripe API key
stripe.api_key = os.getenv('STRIPE_PRIVATE_KEY')


async def create_customer(token: str):
    try:
        customer = stripe.Customer.create(
            source=token
        )

        return {"customer_id": customer.id}

    except stripe.error.StripeError as e:
        # Handle Stripe API errors
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Handle other errors
        raise HTTPException(status_code=500, detail=str(e))

async def create_subscription(customer_id: str, plan_id: str):
    try:
        # Create a subscription using the customer ID and plan ID
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": plan_id}]
        )

        return {"subscription": subscription}

    except stripe.error.StripeError as e:
        # Handle Stripe API errors
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Handle other errors
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/create_subscription")
async def create_subscription(plan: str, token: str):
    price_id = ""
    if plan == 'start':
        price_id = os.getenv('STRIPE_PRICE_START')
    elif plan == 'medium':
        price_id = os.getenv('STRIPE_PRICE_MEDIUM')
    elif plan == 'enterprise':
        price_id = os.getenv('STRIPE_PRICE_ENTERPRISE')
    try:

        # Create Customer
        customer_id = await create_customer(token=token)
        # Create the subscription 
        subscription= await create_subscription(customer_id=customer_id, plan_id=price_id)

        return {"message": "Subscription created successfully!", "subscription_id": subscription.id}

    except stripe.error.CardError as e:
        # Handle card error (e.g., declined card)
        raise HTTPException(status_code=400, detail=e.user_message)

    except Exception as e:
        # Handle other errors
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/udpate_subscription")
async def update_subscription(subscription_id: str, new_plan: str):
    
    new_price_id = ""
    if new_plan == 'start':
        price_id = os.getenv('STRIPE_PRICE_START')
    elif new_plan == 'medium':
        price_id = os.getenv('STRIPE_PRICE_MEDIUM')
    elif new_plan == 'enterprise':
        price_id = os.getenv('STRIPE_PRICE_ENTERPRISE')
    try:
        # Retrieve the subscription to get the current items
        subscription = stripe.Subscription.retrieve(subscription_id)

        # Update the items with the new price ID
        updated_subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{"id": subscription['items']['data'][0].id, "price": new_price_id}]
        )

        return {"updated_subscription": updated_subscription.id}

    except stripe.error.StripeError as e:
        # Handle Stripe API errors
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Handle other errors
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel_subscription")
async def cancel_subscription(subscription_id: str):
    try:
        # Cancel the subscription using the stripe.Subscription.delete method
        subscription = stripe.Subscription.delete(subscription_id)

        return {"message": "Subscription canceled successfully!"}

    except stripe.error.StripeError as e:
        # Handle Stripe API errors
        raise HTTPException(status_code=400, detail=e.user_message)

    except Exception as e:
        # Handle other errors
        raise HTTPException(status_code=500, detail=str(e))

