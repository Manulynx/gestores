class Carro:
    def __init__(self, request):
        self.request = request
        self.session = request.session
        carro = self.session.get('carro')
        if not carro:
            carro = self.session['carro'] = {}
        self.carro = carro

    def agregar(self, material, cantidad=1):
        return self.actualizar_cantidad(material, cantidad)

    def actualizar_cantidad(self, material, cantidad):
        material_id = str(material.id)
        precio_unitario = float(material.precio_actual)
        nueva_cantidad = cantidad
        
        if material.cantidad < nueva_cantidad:
            return False
        
        precio_total = precio_unitario * nueva_cantidad
        
        self.carro[material_id] = {
            'material_id': material.id,
            'nombre': material.nombre,
            'precio_unitario': precio_unitario,  # ✅ Mantener como float
            'precio': precio_total,  # ✅ Mantener como float
            'cantidad': nueva_cantidad,
            'imagen': material.imagen.url,
            'en_oferta': material.en_oferta,
            'precio_regular': float(material.precio)  # ✅ Mantener como float
        }
        self.guardar_carro()
        return True

    def guardar_carro(self):
        self.session['carro'] = self.carro
        self.session.modified = True

    def eliminar(self, material):
        material_id = str(material.id)
        if material_id in self.carro:
            del self.carro[material_id]
            self.guardar_carro()

    def restar_material(self, material):
        material_id = str(material.id)
        if material_id in self.carro:
            nueva_cantidad = self.carro[material_id]['cantidad'] - 1
            if nueva_cantidad > 0:
                self.actualizar_cantidad(material, nueva_cantidad)
            else:
                self.eliminar(material)

    def limpiar_carro(self):
        self.session['carro'] = {}
        self.session.modified = True