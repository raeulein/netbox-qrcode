import base64
from io import BytesIO

from packaging import version
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from netbox.plugins import PluginTemplateExtension
from .template_content_functions import create_text, create_url, config_for_modul, create_QRCode, mm2px, mm2csspx

from django.contrib import messages
from django.template.loader import render_to_string
from .printing import (
    print_label_from_html, _get_printer_cfg, _LABEL_SPECS, extract_label_html, render_html_to_png
)

# ******************************************************************************************
# Contains the main functionalities of the plugin and thus creates the content for the 
# individual modules, e.g: Device, Rack etc.
# ******************************************************************************************

##################################
# Class for creating the plugin content
class QRCode(PluginTemplateExtension):

    ##################################          
    # Creates a plug-in view for a label.
    # --------------------------------
    # Parameter:
    #   labelDesignNo: Which label design should be loaded.
    def Create_SubPluginContent(self, labelDesignNo):

        thisSelf = self

        obj = self.context['object'] # An object of the type Device, Rack etc.

        # Config suitable for the module
        config = config_for_modul(thisSelf, labelDesignNo)

        # Abort if no config data. 
        if config is None: 
            return '' 

        # Get URL for QR code
        url = create_url(thisSelf, config, obj)

        # Create a QR code
        qrCode = create_QRCode(url, config)

        # Create the text for the label if required.
        text = create_text(config, obj, qrCode)

        request = self.context['request'] 

        # -------- Direktdruck ODER Vorschau ----------
        if request.GET.get("direct_print") == str(labelDesignNo) or \
           request.GET.get("show_png")     == str(labelDesignNo) or \
           request.GET.get("show_pdf")  == str(labelDesignNo):


            # 0) Breite/Höhe des Ziel-Labels in px (Brother-Spezifikation)
            p_cfg, code = _get_printer_cfg()
            spec = _LABEL_SPECS[code]
            #width_px, height_px = (spec, spec * 4) if isinstance(spec, int) else spec
                    
            width_px, height_px = (
                (spec, spec * 4) if isinstance(spec, int) else spec
            )

            #Tausche Breite/Höhe, weil Drucker im Hochformat druckt
            width_mm = height_px / 300 * 25.4  # mm für WeasyPrint
            height_mm = width_px / 300 * 25.4  # mm für WeasyPrint

            # 1) mm-Angaben → px-Strings bei 300 dpi
            def _mm_to_px_str(val):
                if isinstance(val, str) and val.endswith("mm"):
                    return f"{mm2px(val)}px"
                return val
            

            px_cfg = {k: _mm_to_px_str(v) for k, v in config.items()}
            px_cfg["label_width"]  = mm2csspx(px_cfg["label_width"])
            px_cfg["label_height"] = mm2csspx(px_cfg["label_height"])

            # 2) qrcode3.html rendern (Card + Label-DIV)
            rendered = render_to_string(
                "netbox_qrcode/qrcode3.html",
                {
                    **px_cfg,
                    "object": obj,
                    "labelDesignNo": labelDesignNo,
                    "qrCode": qrCode,
                    "text": text,
                },
                request=request,
            )

            div_id = f"QR-Code-Label_{labelDesignNo}"
            html_label = extract_label_html(rendered, div_id, width_px, height_px)

            # --- PNG-Vorschau? -------------------------------------------
            if request.GET.get("show_png") == str(labelDesignNo):
                # HTML → PNG
                buf = BytesIO()
                render_html_to_png(html_label, width_mm, height_mm).save(buf, format="PNG")
                data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
                # Bild als ganz normales <img> zurückgeben
                return f'<img src="{data_uri}" alt="Label Preview" style="max-width:100%;border:1px solid #ccc"/>'
            
            if request.GET.get("show_pdf") == str(labelDesignNo):
                # HTML → PDF
                pdf_bytes = render_html_to_png(html_label, width_mm, height_mm, want_pdf=True)
                # PDF einbetten aus BytesIO

                data_uri = "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode()
                return f'<object data="{data_uri}" type="application/pdf" style="width:100%;height:600px;border:1px solid #ccc">\
                        <p>Ihr Browser kann keine eingebetteten PDFs anzeigen.\n\
                        <a href="{data_uri}">PDF herunterladen</a></p>\
                    </object>'
            # ---------------------------------------------------------------

            # 4) Drucken
            try:
                print_label_from_html(html_label, code)
                messages.success(request, "Label wurde gedruckt.")
            except Exception as exc:
                messages.error(request, f"Druckfehler: {exc}")



        # Create plugin using template
        try:
            if version.parse(settings.RELEASE.version).major >= 3:

                render = self.render(
                    'netbox_qrcode/qrcode3.html', extra_context={
                                                                    'object': obj,
                                                                    'title': config.get('title'),
                                                                    'labelDesignNo': labelDesignNo,
                                                                    'qrCode': qrCode, 
                                                                    'with_text': config.get('with_text'),
                                                                    'text': text,
                                                                    'text_location': config.get('text_location'),
                                                                    'text_align_horizontal': config.get('text_align_horizontal'),
                                                                    'text_align_vertical': config.get('text_align_vertical'),
                                                                    'font': config.get('font'),
                                                                    'font_size': config.get('font_size'),
                                                                    'font_weight': config.get('font_weight'),
                                                                    'font_color': config.get('font_color'),
                                                                    'with_qr': config.get('with_qr'),
                                                                    'label_qr_width': config.get('label_qr_width'),
                                                                    'label_qr_height': config.get('label_qr_height'),
                                                                    'label_qr_text_distance': config.get('label_qr_text_distance'),
                                                                    'label_width': config.get('label_width'),
                                                                    'label_height': config.get('label_height'), 
                                                                    'label_edge_top': config.get('label_edge_top'),
                                                                    'label_edge_left': config.get('label_edge_left'),
                                                                    'label_edge_right': config.get('label_edge_right'),
                                                                    'label_edge_bottom': config.get('label_edge_bottom')
                                                                }

                )
            
                return render
            else:
                # Versions 1 and 2 are no longer supported.
                return self.render(
                    'netbox_qrcode/qrcode.html', extra_context={'image': qrCode}
                )
        except ObjectDoesNotExist:
            return ''

    ##################################
    # Create plugin content
    # - First, a plugin view is created for the first label.
    # - If there are further configuration entries for the object/model (e.g. device, rack etc.),
    #   further label views are also created as additional plugin views.
    def Create_PluginContent(self):

        request = self.context['request']

        # --- PNG-Preview: direkt 1:1 zurückgeben -------------------------
        if request.GET.get("show_png"):
            label_no = int(request.GET["show_png"])
            return QRCode.Create_SubPluginContent(self, label_no)
        # -----------------------------------------------------------------

        # First Plugin Content
        pluginContent = QRCode.Create_SubPluginContent(self, 1)

        # Check whether there is another configuration for the object, e.g. device, rack, etc.
        # Support up to 10 additional label configurations (objectName_2 to ..._10) per object (e.g. device, rack, etc.).

        config = self.context['config'] # Django configuration

        for i in range(2, 11):

            configName = self.models[0].replace('dcim.', '') + '_' + str(i)
            obj_cfg = config.get(configName) # Load configuration for additional label if possible.

            if(obj_cfg):
                pluginContent += QRCode.Create_SubPluginContent(self, i) # Add another plugin view
            else:
                break
        
        return pluginContent
    
##################################
# The following section serves to integrate the plugin into Netbox Core.
        
# Class for creating a QR code for the model: Device
class DeviceQRCode(QRCode):
    models = ('dcim.device',)

    def right_page(self):
        return self.Create_PluginContent()

# Class for creating a QR code for the model: Rack
class RackQRCode(QRCode):
    models = ('dcim.rack',)

    def right_page(self):
        return self.Create_PluginContent()

# Class for creating a QR code for the model: Cable
class CableQRCode(QRCode):
    models = ('dcim.cable',)

    def left_page(self):
        return self.Create_PluginContent()

# Class for creating a QR code for the model: Location
class LocationQRCode(QRCode):
    models = ('dcim.location',)

    def left_page(self):
        return self.Create_PluginContent()

# Class for creating a QR code for the model: Power Feed
class PowerFeedQRCode(QRCode):
    models = ('dcim.powerfeed',)

    def right_page(self):
        return self.Create_PluginContent()

# Class for creating a QR code for the model: Power Panel
class PowerPanelQRCode(QRCode):
    models = ('dcim.powerpanel',)

    def right_page(self):
        return self.Create_PluginContent()

# Class for dcim.module
class ModuleQRCode(QRCode):
    models = ('dcim.module',)

    def right_page(self):
        return self.Create_PluginContent()

##################################
# Other plugins support

# Commenting out (for now) - make this work on core models first.
# Class for creating a QR code for the Plugin: Netbox-Inventory (https://github.com/ArnesSI/netbox-inventory)
#class Plugin_Netbox_Inventory(QRCode):
#    models = ()'netbox_inventory.asset' # Info for Netbox in which model the plugin should be integrated.
#
#    def right_page(self):
#        return self.Create_PluginContent()

# Connects Netbox Core with the plug-in classes
# Removed , Plugin_Netbox_Inventory]
template_extensions = [DeviceQRCode, ModuleQRCode, RackQRCode, CableQRCode, LocationQRCode, PowerFeedQRCode, PowerPanelQRCode]