"""
Enterprise UI Components & Toast System
קומפוננטים ומערכת הודעות ברמה אנטרפרייז
"""

def render_loading_skeleton(content_type="table"):
    """Professional loading skeletons for different content types"""
    
    if content_type == "table":
        return '''
        <div class="animate-pulse" id="loading-skeleton">
            <div class="space-y-3">
                <!-- Table header skeleton -->
                <div class="flex space-x-4 p-4 bg-gray-50 rounded-t-lg">
                    <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                    <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                    <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                    <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                </div>
                <!-- Table rows skeleton -->
                <div class="space-y-2 p-4">
                    <div class="flex space-x-4">
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                    </div>
                    <div class="flex space-x-4">
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                    </div>
                    <div class="flex space-x-4">
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                    </div>
                </div>
            </div>
        </div>
        '''
    elif content_type == "cards":
        return '''
        <div class="animate-pulse grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" id="loading-skeleton">
            <div class="bg-white rounded-lg shadow p-6 space-y-3">
                <div class="h-4 bg-gray-200 rounded w-3/4"></div>
                <div class="h-4 bg-gray-200 rounded w-1/2"></div>
                <div class="h-8 bg-gray-200 rounded w-full"></div>
            </div>
            <div class="bg-white rounded-lg shadow p-6 space-y-3">
                <div class="h-4 bg-gray-200 rounded w-3/4"></div>
                <div class="h-4 bg-gray-200 rounded w-1/2"></div>
                <div class="h-8 bg-gray-200 rounded w-full"></div>
            </div>
            <div class="bg-white rounded-lg shadow p-6 space-y-3">
                <div class="h-4 bg-gray-200 rounded w-3/4"></div>
                <div class="h-4 bg-gray-200 rounded w-1/2"></div>
                <div class="h-8 bg-gray-200 rounded w-full"></div>
            </div>
        </div>
        '''
    elif content_type == "form":
        return '''
        <div class="animate-pulse max-w-2xl mx-auto" id="loading-skeleton">
            <div class="space-y-4 p-6 bg-white rounded-lg shadow">
                <div class="h-4 bg-gray-200 rounded w-1/3"></div>
                <div class="h-10 bg-gray-200 rounded"></div>
                <div class="h-4 bg-gray-200 rounded w-1/4"></div>
                <div class="h-10 bg-gray-200 rounded"></div>
                <div class="flex space-x-3 pt-4">
                    <div class="h-10 bg-gray-200 rounded w-24"></div>
                    <div class="h-10 bg-gray-200 rounded w-24"></div>
                </div>
            </div>
        </div>
        '''
    
    # Default loading
    return '''
    <div class="flex items-center justify-center p-8" id="loading-skeleton">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span class="mr-3 text-gray-600">טוען...</span>
    </div>
    '''

def render_toast_message(message_type, title, description="", action_url="", action_text=""):
    """Professional toast notifications"""
    
    icons = {
        'success': '✅',
        'error': '❌', 
        'warning': '⚠️',
        'info': 'ℹ️'
    }
    
    colors = {
        'success': 'bg-green-50 border-green-200 text-green-800',
        'error': 'bg-red-50 border-red-200 text-red-800',
        'warning': 'bg-yellow-50 border-yellow-200 text-yellow-800',
        'info': 'bg-blue-50 border-blue-200 text-blue-800'
    }
    
    color_class = colors.get(message_type, colors['info'])
    icon = icons.get(message_type, icons['info'])
    
    html = f'''
    <div class="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 max-w-md w-full" id="toast-message">
        <div class="border rounded-lg p-4 {color_class} shadow-lg">
            <div class="flex items-start">
                <span class="flex-shrink-0 ml-3">{icon}</span>
                <div class="flex-grow">
                    <h4 class="font-medium">{title}</h4>
                    {'<p class="text-sm mt-1">' + description + '</p>' if description else ''}
                    {'<a href="' + action_url + '" class="text-sm underline mt-2 block">' + action_text + '</a>' if action_url else ''}
                </div>
                <button onclick="document.getElementById('toast-message').remove()" class="flex-shrink-0 mr-3 text-gray-400 hover:text-gray-600">
                    ✕
                </button>
            </div>
        </div>
    </div>
    <script>
        setTimeout(function() {
            var toast = document.getElementById('toast-message');
            if (toast) {
                toast.style.opacity = '0';
                setTimeout(function() { toast.remove(); }, 300);
            }
        }, 5000);
    </script>
    '''
    
    return html

def render_error_state(error_message, retry_url="", retry_text="נסה שוב"):
    """Professional error states with retry options"""
    
    return f'''
    <div class="text-center p-8 bg-red-50 rounded-lg border border-red-200">
        <div class="text-red-600 text-4xl mb-4">⚠️</div>
        <h3 class="text-lg font-medium text-red-800 mb-2">משהו השתבש</h3>
        <p class="text-red-700 mb-4">{error_message}</p>
        {'<button hx-get="' + retry_url + '" hx-target="#main-content" class="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700">' + retry_text + '</button>' if retry_url else ''}
        <p class="text-sm text-red-600 mt-4">אם הבעיה נמשכת, פנה לתמיכה טכנית</p>
    </div>
    '''

def render_empty_state(title, description, action_url="", action_text=""):
    """Professional empty states with call-to-action"""
    
    return f'''
    <div class="text-center p-12 bg-gray-50 rounded-lg border border-gray-200">
        <div class="text-gray-400 text-6xl mb-4">📋</div>
        <h3 class="text-lg font-medium text-gray-900 mb-2">{title}</h3>
        <p class="text-gray-600 mb-6">{description}</p>
        {'<button hx-get="' + action_url + '" hx-target="#main-content" class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">' + action_text + '</button>' if action_url else ''}
    </div>
    '''

def render_form_validation_errors(errors):
    """Render form validation errors professionally"""
    if not errors:
        return ""
        
    html_parts = ['<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">']
    html_parts.append('<h4 class="text-red-800 font-medium mb-2">שגיאות טופס:</h4>')
    html_parts.append('<ul class="list-disc list-inside text-red-700 space-y-1">')
    
    for field, message in errors.items():
        html_parts.append(f'<li>{field}: {message}</li>')
    
    html_parts.append('</ul></div>')
    
    return ''.join(html_parts)