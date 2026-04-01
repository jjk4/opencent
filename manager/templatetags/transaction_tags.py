from django import template

register = template.Library()

@register.simple_tag
def get_transaction_color(transaction):
    """Gibt die passende CSS-Klasse für eine Transaktion zurück."""
    if transaction.has_refunds:
        return "list-group-item-secondary text-decoration-line-through opacity-75" if transaction.is_fully_refunded else "list-group-item-danger"
    if transaction.is_refund:
        return "list-group-item-secondary text-decoration-line-through opacity-75" if transaction.remainder_of_refund == 0 else "list-group-item-success"
    
    if transaction.receiver.is_mine and not transaction.sender.is_mine:
        return "list-group-item-success"
    if transaction.sender.is_mine and not transaction.receiver.is_mine:
        return "list-group-item-danger"
        
    return "list-group-item-secondary"