"""Two simple smoke tests"""
import sqlite3
from setup_db import initialize
from repository import StoreRepository
from cart import ShoppingCart
from payments import FakePaymentGateway
from checkout import CheckoutService
import pytest

@pytest.fixture
def cart(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    return ShoppingCart('user', StoreRepository(str(db)))


def test_seed_product(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    assert StoreRepository(str(db)).get_product('MOU-01').name == 'Wireless mouse'


def test_cart_adds_valid_item(cart):
    assert cart.add_item('USB-01', 2)
    assert len(cart.lines) == 1

# 1. Reject invalid quantities for add_item 
def test_add_item_rejects_invalid_quantities(cart):
    for quantity in (0, -5, 5.4, "2", True, False, None):
        assert cart.add_item("USB-01", quantity) is False
        assert cart.lines == []
    
# 2. Reject invalid quantities for remove_item
def test_remove_item_rejects_invalid_quantities(cart):
    assert cart.add_item("USB-01", 3)

    for quantity in (0, -5, 5.4, "2", True, False):
        assert cart.remove_item("USB-01", quantity) is False
        assert len(cart.lines) == 1
        assert cart.lines[0].quantity == 3

# 3. The stock comparison checks only the new quantity
def test_add_item_checks_cumulative_stock(cart):
    assert cart.add_item("USB-01", 30)
    assert cart.add_item("USB-01", 30) is False
    assert cart.lines[0].quantity == 30

# 4. Discount codes do not stack
def test_discount_codes_do_not_stack(cart):
    assert cart.add_item("USB-01", 2)

    assert cart.apply_discount("WELCOME10") is True
    assert round(cart.total(), 2) == 17.98

    assert cart.apply_discount("WELCOME10") is True
    assert round(cart.total(), 2) == 17.98

    assert cart.apply_discount("STUDENT20") is True
    assert round(cart.total(), 2) == 15.98


# 5. Discount total updates after cart changes
def test_discount_total_updates_after_cart_changes(cart):
    assert cart.add_item("USB-01", 2)
    assert cart.apply_discount("WELCOME10") is True

    assert cart.add_item("USB-01", 1)
    assert round(cart.total(), 2) == 26.97

    assert cart.remove_item("USB-01", 1)
    assert round(cart.total(), 2) == 17.98

# 6. SAVE15 must not make a cart negative.
def test_save15_total_cannot_be_negative(cart):
    cart.add_item('USB-01', 1)

    assert cart.apply_discount('SAVE15')
    assert round(cart.total(), 2) == 0

# 7. Loading the saved cart twice must not duplicate items.
def test_load_does_not_duplicate_items(cart):
    cart.add_item('USB-01', 2)
    cart.save()

    cart.load()
    cart.load()

    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2

# 8. SQL injection attempts must not succeed.
def test_sql_injection_is_blocked(cart):
    repository = cart.repository
    cart.add_item('USB-01', 2)
    cart.save()

    assert repository.get_product("unknown' OR 1=1 --") is None
    assert repository.get_saved_cart("unknown' OR 1=1 --") == []
    assert repository.get_saved_cart('user') == [('USB-01', 2)]

# 9. Each user must only receive their own orders.
def test_orders_are_filtered_by_user(cart):
    repository = cart.repository
    order_id = repository.save_order('user', 10, 'paid', 'order-1')
    repository.save_order('other-user', 20, 'paid', 'order-2')

    orders = repository.list_orders('user')

    assert len(orders) == 1
    assert orders[0][0] == order_id
    assert orders[0][1] == 'user'

# 10. Successful checkout must update stock, clear the cart, and hide the payment token.
def test_successful_checkout(cart, capsys):
    repo = cart.repository
    stock_before = repo.get_product('USB-01').stock
    cart.add_item('USB-01', 2)
    cart.save()

    service = CheckoutService(repo, FakePaymentGateway())
    result = service.checkout(cart, 'TEST_TOKEN', 'request-success')

    assert result.status == 'paid'
    assert repo.get_product('USB-01').stock == stock_before - 2
    assert cart.lines == []
    assert repo.get_saved_cart('user') == []

    captured = capsys.readouterr()
    assert 'TEST_TOKEN' not in captured.out + captured.err
    
# 11. Declines and simulated payment errors must preserve stock and cart.
def test_failed_checkout_keeps_stock_and_cart(cart):
    class ErrorGateway:
        def charge(self, amount, payment_token):
            raise RuntimeError('Simulated payment failure')

    repo = cart.repository
    stock_before = repo.get_product('USB-01').stock
    cart.add_item('USB-01', 2)
    cart.save()

    for gateway, status in [
        (FakePaymentGateway(False), 'declined'),
        (ErrorGateway(), 'payment_error')
    ]:
        service = CheckoutService(repo, gateway)
        result = service.checkout(cart, 'TEST_TOKEN', status)

        assert result.status == status
        assert repo.get_product('USB-01').stock == stock_before
        assert len(cart.lines) == 1
        assert cart.lines[0].quantity == 2
        assert repo.get_saved_cart('user') == [('USB-01', 2)]
        
# 12. Missing request IDs must stop checkout before payment.
def test_missing_request_id(cart):
    repo = cart.repository
    cart.add_item('USB-01', 2)
    gateway = FakePaymentGateway(should_approve=True)
    service = CheckoutService(repo, gateway)

    for request_id in [None, '']:
        result = service.checkout(cart, 'TEST_TOKEN', request_id)
        assert result.status == 'missing_request_id'
    
    assert gateway.calls == []
