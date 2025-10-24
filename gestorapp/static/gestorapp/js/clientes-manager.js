/**
 * Módulo de gestión de clientes
 * Proporciona funcionalidades para gestionar clientes desde otros módulos
 */

class ClientesManager {
    constructor() {
        this.apiBaseUrl = '/clientes/';
        this.isInitialized = false;
    }

    init() {
        if (this.isInitialized) return;
        
        this.setupGlobalEventListeners();
        this.isInitialized = true;
    }

    setupGlobalEventListeners() {
        // Escuchar solicitudes para abrir modal de cliente
        document.addEventListener('abrirModalCliente', () => {
            this.abrirModalCrearCliente();
        });

        // Escuchar cuando se crea un nuevo cliente
        document.addEventListener('clienteCreado', (e) => {
            console.log('Cliente creado:', e.detail);
        });
    }

    /**
     * Buscar cliente por carnet de identidad
     */
    async buscarPorCarnet(carnet) {
        try {
            const response = await fetch(`${this.apiBaseUrl}buscar/${carnet}/`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            return await response.json();
        } catch (error) {
            console.error('Error buscando cliente:', error);
            return { status: 'error', message: 'Error de conexión' };
        }
    }

    /**
     * Buscar clientes con autocompletado
     */
    async buscarClientes(query) {
        try {
            const response = await fetch(`${this.apiBaseUrl}buscar-ajax/?q=${encodeURIComponent(query)}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            return data.clientes || [];
        } catch (error) {
            console.error('Error buscando clientes:', error);
            return [];
        }
    }

    /**
     * Crear nuevo cliente mediante AJAX
     */
    async crearCliente(datosCliente) {
        try {
            const formData = new FormData();
            Object.keys(datosCliente).forEach(key => {
                formData.append(key, datosCliente[key]);
            });

            const response = await fetch(`${this.apiBaseUrl}crear-modal/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            return await response.json();
        } catch (error) {
            console.error('Error creando cliente:', error);
            return { status: 'error', message: 'Error de conexión' };
        }
    }

    /**
     * Abrir modal para crear cliente
     */
    async abrirModalCrearCliente() {
        // Verificar si el modal ya existe
        let modal = document.getElementById('crearClienteModal');
        
        if (!modal) {
            // Cargar el modal mediante AJAX
            try {
                const response = await fetch(`${this.apiBaseUrl}crear-modal/`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                const html = await response.text();
                
                // Crear un contenedor temporal
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = html;
                modal = tempDiv.querySelector('#crearClienteModal');
                
                if (modal) {
                    document.body.appendChild(modal);
                } else {
                    throw new Error('Modal no encontrado en la respuesta');
                }
            } catch (error) {
                console.error('Error cargando modal:', error);
                this.mostrarError('Error al cargar el formulario de cliente');
                return;
            }
        }

        // Mostrar el modal
        const modalInstance = new bootstrap.Modal(modal);
        modalInstance.show();
    }

    /**
     * Validar datos de cliente
     */
    validarDatosCliente(datos) {
        const errores = {};

        if (!datos.nombre || datos.nombre.trim().length < 2) {
            errores.nombre = ['El nombre debe tener al menos 2 caracteres'];
        }

        if (!datos.apellidos || datos.apellidos.trim().length < 2) {
            errores.apellidos = ['Los apellidos deben tener al menos 2 caracteres'];
        }

        if (!datos.carnet_identidad || datos.carnet_identidad.length !== 11) {
            errores.carnet_identidad = ['El carnet debe tener exactamente 11 caracteres'];
        }

        if (!datos.telefono || datos.telefono.trim().length < 8) {
            errores.telefono = ['El teléfono debe tener al menos 8 caracteres'];
        }

        return Object.keys(errores).length === 0 ? null : errores;
    }

    /**
     * Crear selector de clientes en un contenedor específico
     */
    crearSelector(containerId, opciones = {}) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('Contenedor no encontrado:', containerId);
            return null;
        }

        // Cargar el HTML del selector
        this.cargarSelectorHTML(container).then(() => {
            // Inicializar el selector
            const selector = new ClienteSelector(containerId, opciones);
            return selector;
        });
    }

    /**
     * Cargar HTML del selector de clientes
     */
    async cargarSelectorHTML(container) {
        const html = `
            <div class="cliente-selector">
                <div class="form-group">
                    <label for="cliente-search" class="form-label">
                        <i class="fas fa-user"></i> Buscar Cliente
                    </label>
                    <div class="input-group">
                        <input type="text" 
                               id="cliente-search" 
                               class="form-control" 
                               placeholder="Buscar por nombre, carnet o teléfono..."
                               autocomplete="off">
                        <button type="button" class="btn btn-outline-primary" id="btn-nuevo-cliente">
                            <i class="fas fa-plus"></i> Nuevo
                        </button>
                    </div>
                    
                    <div id="cliente-dropdown" class="dropdown-menu w-100" style="display: none;">
                        <div id="cliente-results"></div>
                        <div class="dropdown-divider"></div>
                        <a class="dropdown-item text-center text-muted" href="#" id="no-results" style="display: none;">
                            <i class="fas fa-search"></i> No se encontraron clientes
                        </a>
                    </div>
                    
                    <div id="cliente-selected" class="mt-2" style="display: none;">
                        <div class="card border-success">
                            <div class="card-body py-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <strong id="cliente-nombre"></strong><br>
                                        <small class="text-muted">
                                            CI: <span id="cliente-carnet"></span> | 
                                            Tel: <span id="cliente-telefono"></span>
                                        </small>
                                    </div>
                                    <button type="button" class="btn btn-outline-danger btn-sm" id="btn-clear-cliente">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                        <input type="hidden" id="cliente-id" name="cliente_id" value="">
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    /**
     * Utilidades
     */
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }

    mostrarError(mensaje) {
        // Implementar según el sistema de notificaciones de la app
        console.error(mensaje);
        alert(mensaje); // Temporal
    }

    mostrarExito(mensaje) {
        // Implementar según el sistema de notificaciones de la app
        console.log(mensaje);
        alert(mensaje); // Temporal
    }

    /**
     * Formatear datos de cliente para mostrar
     */
    formatearCliente(cliente) {
        return {
            id: cliente.id,
            nombre_completo: cliente.nombre_completo || `${cliente.nombre} ${cliente.apellidos}`,
            carnet_identidad: cliente.carnet_identidad,
            telefono: cliente.telefono,
            nombre: cliente.nombre,
            apellidos: cliente.apellidos
        };
    }
}

// Instancia global del manager
const clientesManager = new ClientesManager();

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    clientesManager.init();
});

// Exportar para uso en otros módulos
window.ClientesManager = ClientesManager;
window.clientesManager = clientesManager;