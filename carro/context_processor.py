
def importe_total_carro(request):
    total = 0
    if request.user.is_authenticated:
        for key, value in request.session.get('carro', {}).items():
            total += float(value['precio'])
    else:
        total = 'Inicia sesión para ver el importe total'
    return {'importe_total_carro': total}
