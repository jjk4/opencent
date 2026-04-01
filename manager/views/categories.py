from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.db.models import ProtectedError

from ..models import Category, Transaction
from ..forms import CategoryForm


@login_required
def categories(request):
    categories = Category.objects.filter(parent_category__isnull=True, user=request.user)
    context = {
        'header_data': {
            'title': _('Categories'),
            'selected_tab': 'categories',
        },
        'categories': categories,
    }
    return render(request, 'categories/index.html', context)

@login_required
def category_detail(request, category_id):
    category = Category.objects.get(id=category_id, user=request.user)
    context = {
        'header_data': {
            'title': f"{category.name} {_('Details')}",
            'selected_tab': 'categories',
        },
        'category': category,
    }
    return render(request, 'categories/detail.html', context)

@login_required
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, user=request.user)
        
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            return redirect('categories') 
    else:
        form = CategoryForm(user=request.user)
    
    context = {
        'header_data': {
            'title': _('New Category'),
            'selected_tab': 'categories',
        },
        'form': form,
    }
    return render(request, 'categories/add.html', context)

@login_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('categories')
    else:
        form = CategoryForm(instance=category, user=request.user)
    
    context = {
        'header_data': {
            'title': _('Edit Category'),
            'selected_tab': 'categories',
        },
        'form': form,
        'is_edit': True
    }
    return render(request, 'categories/add.html', context)

@login_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id, user=request.user)

    if request.method == 'POST':
        try:
            category.delete()
        except ProtectedError:
            error = _("This category cannot be deleted because it is still assigned to transactions. Please remove the category from all assigned transactions before deleting it.")
            transactions = Transaction.objects.filter(user=request.user, categories=category).all()
        else:
            return redirect('categories')            
        
        
    context = {
         'header_data': {
            'title': _('Delete Category'),
            'selected_tab': 'categories',
        },
        'category': category,
        'error': error if 'error' in locals() else None,
        'transactions': transactions if 'transactions' in locals() else None,
    }
    return render(request, 'categories/delete.html', context)