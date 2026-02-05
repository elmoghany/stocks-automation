"""Programmatic E*TRADE API wrapper -- no interactive input() calls.

Replicates the same HTTP calls as the existing etrade_python_client but
exposes them as plain method calls suitable for automated trading.
"""

import configparser
import json
import logging
import random
import webbrowser
from logging.handlers import RotatingFileHandler

from rauth import OAuth1Service

from trading.config import (
    CONFIG_INI_PATH,
    ETRADE_AUTH_BASE,
    ETRADE_AUTHORIZE_URL,
    QUOTE_BATCH_SIZE,
    SANDBOX_BASE_URL,
    PROD_BASE_URL,
)

logger = logging.getLogger("trading")


class ETradeSession:
    """Manages OAuth1 authentication and provides API helper methods."""

    def __init__(self, sandbox: bool = True):
        config = configparser.ConfigParser()
        config.read(CONFIG_INI_PATH)
        self.consumer_key = config["DEFAULT"]["CONSUMER_KEY"]
        self.consumer_secret = config["DEFAULT"]["CONSUMER_SECRET"]
        self.base_url = SANDBOX_BASE_URL if sandbox else PROD_BASE_URL
        self.session = None
        self._service = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def authenticate(self) -> None:
        """Run the full OAuth1 flow (opens browser, requires verifier)."""
        self._service = OAuth1Service(
            name="etrade",
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            request_token_url=f"{ETRADE_AUTH_BASE}/oauth/request_token",
            access_token_url=f"{ETRADE_AUTH_BASE}/oauth/access_token",
            authorize_url=ETRADE_AUTHORIZE_URL,
            base_url=ETRADE_AUTH_BASE,
        )

        # Step 1 -- request token
        request_token, request_token_secret = self._service.get_request_token(
            params={"oauth_callback": "oob", "format": "json"}
        )

        # Step 2 -- user authorizes in browser
        authorize_url = self._service.authorize_url.format(
            self._service.consumer_key, request_token
        )
        webbrowser.open(authorize_url)
        text_code = input(
            "Please accept agreement and enter verification code from browser: "
        )

        # Step 3 -- exchange for access token
        self.session = self._service.get_auth_session(
            request_token,
            request_token_secret,
            params={"oauth_verifier": text_code},
        )
        logger.info("OAuth authentication successful")

    def renew_token(self) -> bool:
        """Renew the access token to keep the session alive."""
        url = f"{ETRADE_AUTH_BASE}/oauth/renew_access_token"
        try:
            resp = self.session.get(url, header_auth=True)
            if resp.status_code == 200:
                logger.info("Access token renewed")
                return True
            logger.warning("Token renewal failed: %s", resp.status_code)
            return False
        except Exception:
            logger.exception("Token renewal error")
            return False

    # ------------------------------------------------------------------
    # Account helpers
    # ------------------------------------------------------------------
    def get_account_list(self) -> list:
        """Return list of non-CLOSED account dicts."""
        url = f"{self.base_url}/v1/accounts/list.json"
        resp = self.session.get(url, header_auth=True)
        if resp.status_code != 200:
            logger.error("account_list failed: %s", resp.text)
            return []
        data = resp.json()
        accounts = (
            data.get("AccountListResponse", {})
            .get("Accounts", {})
            .get("Account", [])
        )
        return [a for a in accounts if a.get("accountStatus") != "CLOSED"]

    def get_balance(self, account: dict) -> dict:
        """Return balance info for the given account."""
        url = (
            f"{self.base_url}/v1/accounts/"
            f"{account['accountIdKey']}/balance.json"
        )
        params = {
            "instType": account.get("institutionType", "BROKERAGE"),
            "realTimeNAV": "true",
        }
        headers = {"consumerkey": self.consumer_key}
        resp = self.session.get(
            url, header_auth=True, params=params, headers=headers
        )
        if resp.status_code != 200:
            logger.error("balance failed: %s", resp.text)
            return {}
        return resp.json().get("BalanceResponse", {})

    def get_portfolio(self, account: dict) -> list:
        """Return list of position dicts for the given account."""
        url = (
            f"{self.base_url}/v1/accounts/"
            f"{account['accountIdKey']}/portfolio.json"
        )
        resp = self.session.get(url, header_auth=True)
        if resp.status_code == 204:
            return []
        if resp.status_code != 200:
            logger.error("portfolio failed: %s", resp.text)
            return []
        data = resp.json()
        positions = []
        for ap in data.get("PortfolioResponse", {}).get("AccountPortfolio", []):
            positions.extend(ap.get("Position", []))
        return positions

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------
    def get_quotes(self, symbols: list) -> dict:
        """Fetch quotes for a list of symbols, batched by QUOTE_BATCH_SIZE.

        Returns dict keyed by symbol with quote data.
        """
        result = {}
        for i in range(0, len(symbols), QUOTE_BATCH_SIZE):
            batch = symbols[i : i + QUOTE_BATCH_SIZE]
            sym_str = ",".join(batch)
            url = f"{self.base_url}/v1/market/quote/{sym_str}.json"
            params = {"detailFlag": "ALL"}
            resp = self.session.get(url, header_auth=True, params=params)
            if resp.status_code != 200:
                logger.error("quote failed for batch %s: %s", sym_str, resp.text)
                continue
            data = resp.json()
            for qd in data.get("QuoteResponse", {}).get("QuoteData", []):
                sym = qd.get("Product", {}).get("symbol")
                if sym:
                    result[sym] = qd
        return result

    # ------------------------------------------------------------------
    # Order helpers
    # ------------------------------------------------------------------
    def preview_order(
        self,
        account: dict,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: float,
        order_term: str = "GOOD_FOR_DAY",
    ) -> dict:
        """Preview a LIMIT equity order. Returns preview response dict."""
        url = (
            f"{self.base_url}/v1/accounts/"
            f"{account['accountIdKey']}/orders/preview.json"
        )
        headers = {
            "Content-Type": "application/xml",
            "consumerKey": self.consumer_key,
        }
        client_order_id = random.randint(1000000000, 9999999999)
        payload = """<PreviewOrderRequest>
            <orderType>EQ</orderType>
            <clientOrderId>{cid}</clientOrderId>
            <Order>
                <allOrNone>false</allOrNone>
                <priceType>LIMIT</priceType>
                <orderTerm>{term}</orderTerm>
                <marketSession>REGULAR</marketSession>
                <stopPrice></stopPrice>
                <limitPrice>{price}</limitPrice>
                <Instrument>
                    <Product>
                        <securityType>EQ</securityType>
                        <symbol>{sym}</symbol>
                    </Product>
                    <orderAction>{act}</orderAction>
                    <quantityType>QUANTITY</quantityType>
                    <quantity>{qty}</quantity>
                </Instrument>
            </Order>
        </PreviewOrderRequest>""".format(
            cid=client_order_id,
            term=order_term,
            price=limit_price,
            sym=symbol,
            act=action,
            qty=quantity,
        )

        resp = self.session.post(url, header_auth=True, headers=headers, data=payload)
        logger.debug("preview_order response: %s", resp.text)
        if resp.status_code != 200:
            logger.error("preview_order failed: %s", resp.text)
            return {}
        return resp.json().get("PreviewOrderResponse", {})

    def place_order(
        self,
        account: dict,
        preview_response: dict,
        symbol: str,
        action: str,
        quantity: int,
        limit_price: float,
        client_order_id: int = None,
        order_term: str = "GOOD_FOR_DAY",
    ) -> dict:
        """Place an order using the preview IDs from preview_order."""
        url = (
            f"{self.base_url}/v1/accounts/"
            f"{account['accountIdKey']}/orders/place.json"
        )
        headers = {
            "Content-Type": "application/xml",
            "consumerKey": self.consumer_key,
        }

        # Extract preview IDs
        preview_ids = preview_response.get("PreviewIds", [])
        if not preview_ids:
            logger.error("No preview IDs available for place_order")
            return {}

        preview_id = preview_ids[0].get("previewId", "")
        if client_order_id is None:
            # Pull from the preview response Order
            orders = preview_response.get("Order", [])
            if orders:
                client_order_id = preview_response.get("clientOrderId", random.randint(1000000000, 9999999999))
            else:
                client_order_id = random.randint(1000000000, 9999999999)

        payload = """<PlaceOrderRequest>
            <orderType>EQ</orderType>
            <clientOrderId>{cid}</clientOrderId>
            <PreviewIds>
                <previewId>{pid}</previewId>
            </PreviewIds>
            <Order>
                <allOrNone>false</allOrNone>
                <priceType>LIMIT</priceType>
                <orderTerm>{term}</orderTerm>
                <marketSession>REGULAR</marketSession>
                <stopPrice></stopPrice>
                <limitPrice>{price}</limitPrice>
                <Instrument>
                    <Product>
                        <securityType>EQ</securityType>
                        <symbol>{sym}</symbol>
                    </Product>
                    <orderAction>{act}</orderAction>
                    <quantityType>QUANTITY</quantityType>
                    <quantity>{qty}</quantity>
                </Instrument>
            </Order>
        </PlaceOrderRequest>""".format(
            cid=client_order_id,
            pid=preview_id,
            term=order_term,
            price=limit_price,
            sym=symbol,
            act=action,
            qty=quantity,
        )

        resp = self.session.post(url, header_auth=True, headers=headers, data=payload)
        logger.debug("place_order response: %s", resp.text)
        if resp.status_code != 200:
            logger.error("place_order failed: %s", resp.text)
            return {}
        return resp.json().get("PlaceOrderResponse", {})
