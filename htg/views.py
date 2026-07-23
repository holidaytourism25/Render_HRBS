from django.shortcuts import render

def home(request):
    """
    Renders the holiday tourism landing page.
    """
    return render(request, 'htg/index.html')