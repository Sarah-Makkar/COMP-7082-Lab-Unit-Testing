# Reliable Programming and Unit Testing Lab

## Defects and Corrections

### 1. Invalid quantities when adding items

**Location:** `cart.py` — `add_item(self, sku, quantity)`

**Problem:** No Quantity Validation - This function accepts zero, negative and non-integer values. A negative quantity gives a negative subtotal, fractional quantities can create fraction item quantity, a string quantity raises a TypeError.

**Correction:** 

```python
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
     if product.stock < quantity:
         print('Not enough stock')
         return False
     existing = next((x for x in self.lines if x.sku == sku), None)
     if existing:
         existing.quantity += quantity
     else:
         self.lines.append(CartLine(sku, product.name, product.price, quantity))
     return True
```

### 2. Invalid quantities when removing items

**Location:** `cart.py` — `remove_item(self, sku, quantity=None)`

**Problem:** No Quantity Validation - This function accepts zero, negative and non-integer values. A negative quantity can increase the item quantity in the cart, removing zero returns true without removing anything, fractional quantities can create fraction item quantity, a string quantity raises a TypeError.

**Correction:** 
```python
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
```

### 3. Cumulative quantities can exceed stock

**Location:** `cart.py` — `add_item(self, sku, quantity)`

**Problem:** The stock comparison checks only the new quantity. For example , with available stock 5, adding 3 items twice succeeded, leaving total of 6 items in the cart.

**Correction:** 

```python
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
```

### 4. Discounts stack and totals become outdated

**Location:** `cart.py` — `apply_discount(self, code)`

**Problem:** The function allows the same coupon to be applied repeatedly or multiple coupons to stack. The discounted total does not update when items are added or removed, and the SAVE15 coupon can produce a negative total.

**Correction:**

```python
VALID_COUPONS = ['WELCOME10', 'STUDENT20', 'SAVE15', 'FREESHIP']

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
```

### 5. Loading a saved cart duplicates items

**Location:** `cart.py` — `load(self)`

**Problem:** The function appends saved items to the cart every time it is called, i.e loading the same cart twice increases quantities instead of restoring the state.

**Correction:** Fetch the saved cart and clear the current lines before restoring them.

```python
def load(self):
    saved_cart = self.repository.get_saved_cart(self.user_id)
    self.lines.clear()
    for sku, quantity in saved_cart:
        self.add_item(sku, quantity)
```

### 6. SQL injection in repository lookups

**Location:** `repository.py` — `get_product(self, sku)` and `get_saved_cart(self, user_id)`

**Problem:** SQL injection in get_product and get_saved_cart

**Correction:** Use parameterized queries

```python
def get_product(self, sku):
    conn = self.connect()
    row = conn.execute('SELECT sku, name, price, stock FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()
    return Product(*row) if row else None

def get_saved_cart(self, user_id):
    conn = self.connect()
    rows = conn.execute('SELECT sku, quantity FROM saved_cart WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return rows
```

### 7. Order listings include other users' orders

**Location:** `repository.py` — `list_orders(self, user_id)`

**Problem:** The function ignores the passed parameter user_id and returns every user’s  orders

**Correction:** 

```python
def list_orders(self, user_id):
    conn = self.connect()
    rows = conn.execute('SELECT id, user_id, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id, )).fetchall()
    conn.close()
    return rows
```

### 8. Checkout changes stock and clears carts after failed payments

**Location:** `checkout.py` — `CheckoutService.checkout()`

**Problem:** Stock is decremented before the payment. Even if payment is declined or runs into error, the stock is decremented. The cart is cleared even when payment fails. It also allowed missing request ID’s. It even printed sensitive payment tokens in logs

**Correction:** Validate the request ID before processing. For the provided payment simulator, deduct stock and clear the cart only after payment is approved. Remove payment-token logging and reset discount details after a successful purchase.

```python
def checkout(self, cart, payment_token, request_id):
    if len(cart.lines) == 0:
        return OrderResult(None, 'empty', 0)
    if not request_id:
        return OrderResult(None, "missing_request_id", 0)

    amount = cart.total()
    
    try:
        response = self.payment_gateway.charge(amount, payment_token)
        status = 'paid' if response['approved'] else 'declined'
    except Exception:
        status = 'payment_error'
    
    if status == "paid":
        for line in cart.lines:
            self.repository.update_stock(line.sku, line.quantity)

    order_id = self.repository.save_order(cart.user_id, amount, status, request_id)
    
    if status == "paid":
        cart.lines.clear()
        cart.discount_code = None
        cart.discounted_total = None
        cart.save()
    return OrderResult(order_id, status, amount)

```
