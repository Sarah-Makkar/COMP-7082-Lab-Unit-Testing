"""Business logic. Several design and correctness issues are intentional."""
from models import CartLine


class ShoppingCart:
    VALID_COUPONS = {"WELCOME10", "STUDENT20", "SAVE15", "FREESHIP"}

    def __init__(self, user_id, repository):
        self.user_id = user_id
        self.repository = repository
        self.lines = []
        self.discount_code = None
        # self.discounted_total = None

    @staticmethod
    def _valid_quantity(quantity):
        return type(quantity) is int and quantity > 0

    def add_item(self, sku, quantity):
        if not self._valid_quantity(quantity):
            print('Invalid quantity')
            return False
        product = self.repository.get_product(sku)
        if not product:
            print('Unknown product')
            return False

        existing = next((x for x in self.lines if x.sku == sku), None)
        new_quantity = quantity + (existing.quantity if existing else 0)
        if product.stock < new_quantity:
            print('Not enough stock')
            return False

        if existing:
            existing.quantity = new_quantity
        else:
            self.lines.append(CartLine(sku, product.name, product.price, quantity))
        return True

    def remove_item(self, sku, quantity=None):
        if quantity is not None and not self._valid_quantity(quantity):
            print('Invalid quantity')
            return False
        for line in self.lines:
            if line.sku == sku:
                if quantity is None or quantity >= line.quantity:
                    self.lines.remove(line)
                else:
                    line.quantity -= quantity
                return True
        print('Item not found')
        return False

    def subtotal(self):
        return sum(line.unit_price * line.quantity for line in self.lines)

    def total(self):
        amount = self.subtotal();
        if self.discount_code == "WELCOME10":
            amount *= 0.9
        elif self.discount_code == "STUDENT20":
            amount *= 0.8
        elif self.discount_code == "SAVE15":
            amount -= 15
        return max(amount, 0)

    def apply_discount(self, code):
        if type(code) is not str or code not in self.VALID_COUPONS:
            print('Invalid coupon')
            return False
        self.discount_code = code
        
        if code == "FREESHIP":
            print("Free shipping applied")

        return True
        
    def load(self):
        saved_cart = self.repository.get_saved_cart(self.user_id)
        self.lines.clear()
        for sku, quantity in saved_cart:
            self.add_item(sku, quantity)

    def save(self):
        self.repository.save_cart(self.user_id, self.lines)
