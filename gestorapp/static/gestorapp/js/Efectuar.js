document.addEventListener('DOMContentLoaded', function() {
    // Función para actualizar la cantidad en pedidos pendientes
    function actualizarCantidadPendientes(materialId) {
        fetch(`/api/material/${materialId}/cantidad-pendiente/`)
            .then(response => response.json())
            .then(data => {
                const cantidadElement = document.querySelector(`#material-${materialId} .text-warning`);
                if (cantidadElement) {
                    cantidadElement.innerHTML = `
                        <i class="fas fa-clock me-1"></i>
                        En Pedidos Pendientes: ${data.cantidad_pendiente}
                    `;
                }
            })
            .catch(error => console.error('Error:', error));
    }

    // Función para efectuar el pedido
    window.efectuarPedido = function(pedidoId) {
        fetch(`/pedidos/efectuar/${pedidoId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Mostrar mensaje de éxito
                showAlert('success', data.message);
                
                // Actualizar las cantidades de los materiales afectados
                if (data.materiales_afectados) {
                    data.materiales_afectados.forEach(materialId => {
                        actualizarCantidadPendientes(materialId);
                    });
                }
            } else {
                showAlert(data.status, data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'Error al procesar la solicitud');
        });
    }

    // Función auxiliar para obtener el token CSRF
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Función para mostrar alertas
    function showAlert(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.role = 'alert';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        document.body.insertBefore(alertDiv, document.body.firstChild);
        
        // Auto-cerrar la alerta después de 3 segundos
        setTimeout(() => {
            alertDiv.remove();
        }, 3000);
    }
});