from datetime import date

from plaid.api import plaid_api
from plaid.api_client import ApiClient
from plaid.configuration import Configuration
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.sandbox_public_token_create_request_options import SandboxPublicTokenCreateRequestOptions
from plaid.model.custom_sandbox_transaction import CustomSandboxTransaction
from plaid.model.sandbox_transactions_create_request import SandboxTransactionsCreateRequest
from kiwi_finance.config import Config


def get_plaid_client():
    host_map = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }

    configuration = Configuration(
        host=host_map.get(Config.PLAID_ENV, "https://sandbox.plaid.com"),
        api_key={
            "clientId": Config.PLAID_CLIENT_ID,
            "secret": Config.PLAID_SECRET,
        },
    )

    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(user_id: str, access_token: str | None = None):
    """
    Create a Link token for connecting or updating Plaid items.
    
    Args:
        user_id: The user's ID
        access_token: Optional access token for update mode (re-authentication)
    """
    client = get_plaid_client()

    request_params = {
        "user": LinkTokenCreateRequestUser(client_user_id=user_id),
        "client_name": "Kiwi Finance",
        "products": [Products("transactions")],
        "country_codes": [CountryCode("US")],
        "language": "en",
    }
    
    # If access_token is provided, use update mode for re-authentication
    if access_token:
        request_params["access_token"] = access_token
    
    request = LinkTokenCreateRequest(**request_params)
    response = client.link_token_create(request)
    return response.to_dict()


def exchange_public_token(public_token: str):
    client = get_plaid_client()

    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = client.item_public_token_exchange(request)
    return response.to_dict()


def get_accounts(access_token: str):
    client = get_plaid_client()

    request = AccountsGetRequest(access_token=access_token)
    response = client.accounts_get(request)
    return response.to_dict()


def get_transactions_sync(access_token: str, cursor: str | None = None):
    client = get_plaid_client()

    if cursor:
        request = TransactionsSyncRequest(
            access_token=access_token,
            cursor=cursor,
        )
    else:
        request = TransactionsSyncRequest(
            access_token=access_token,
        )

    response = client.transactions_sync(request)
    return response.to_dict()

def create_sandbox_item():
    client = get_plaid_client()

    request = SandboxPublicTokenCreateRequest(
        institution_id="ins_109508",
        initial_products=[Products("transactions")],
        options=SandboxPublicTokenCreateRequestOptions(
            override_username="user_transactions_dynamic",
        ),
    )

    response = client.sandbox_public_token_create(request)
    return response.to_dict()


def create_sandbox_transactions(access_token: str, transactions: list[dict]):
    client = get_plaid_client()

    custom_transactions = [
        CustomSandboxTransaction(
            date_transacted=transaction["date_transacted"],
            date_posted=transaction["date_posted"],
            amount=transaction["amount"],
            description=transaction["description"],
            iso_currency_code=transaction.get("iso_currency_code", "USD"),
        )
        for transaction in transactions
    ]

    request = SandboxTransactionsCreateRequest(
        access_token=access_token,
        transactions=custom_transactions,
    )

    response = client.sandbox_transactions_create(request)
    return response.to_dict()
