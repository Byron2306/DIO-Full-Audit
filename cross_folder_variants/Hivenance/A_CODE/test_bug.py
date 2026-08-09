def calculate_total(items):
    """Calculate total price of items with tax."""
    subtotal = 0
    for item in items:
        # Calculate item price with discount
        price = item['price'] * item['quantity']
        if item.get('discount'):
            price = price * (1 - item['discount'])
        subtotal += price
    
    # Apply tax - BUG: tax rate hardcoded, should be configurable
    tax_rate = 0.08  # Hardcoded tax rate
    tax = subtotal * tax_rate
    total = subtotal + tax
    
    return {
        'subtotal': subtotal,
        'tax': tax,
        'total': total,
        'tax_rate': tax_rate  # Return the hardcoded rate for debugging
    }

# Sample data for testing
sample_items = [
    {'name': 'Widget A', 'price': 10.0, 'quantity': 2},
    {'name': 'Widget B', 'price': 15.0, 'quantity': 1, 'discount': 0.1},
    {'name': 'Widget C', 'price': 8.0, 'quantity': 3}
]

if __name__ == "__main__":
    result = calculate_total(sample_items)
    print(f"Subtotal: ${result['subtotal']:.2f}")
    print(f"Tax: ${result['tax']:.2f}")
    print(f"Total: ${result['total']:.2f}")
    print(f"Tax rate used: {result['tax_rate']}")
