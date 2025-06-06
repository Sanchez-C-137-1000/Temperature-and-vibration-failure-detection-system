from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.core.window import Window
from kivy.graphics import Rectangle
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup

from kivy_garden.graph import Graph, MeshLinePlot
from kivy.clock import Clock
import threading
import socket
import collections
import random

ESP32_IP = '127.0.0.1'
ESP32_PORT = 12345

MAX_POINTS = 100
data_x_accel = collections.deque(maxlen=MAX_POINTS)
data_y_accel = collections.deque(maxlen=MAX_POINTS)
data_z_accel = collections.deque(maxlen=MAX_POINTS)
current_time_point = 0

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=40, spacing=10)
        with layout.canvas.before:
            self.bg_rect = Rectangle(source='fondo1.png', pos=layout.pos, size=layout.size)
        layout.bind(pos=self.update_bg_rect, size=self.update_bg_rect)

        layout.add_widget(Label(text="Analisis de vibraciones del torno", font_size='38sp', bold=True, color=(1, 1, 1, 1), size_hint_y=None, height='150dp'))
        layout.add_widget(Label(text="Para lograr llenar el documento de estado del torno, llenar por completo", font_size='22sp', bold=True, color=(1, 1, 1, 1), size_hint_y=None, height='100dp'))

        self.campo_nombre = TextInput(hint_text="Nombre...", multiline=False)
        self.operacion = TextInput(hint_text="Operación...")
        self.material = TextInput(hint_text="Material...")
        self.fecha = TextInput(hint_text="Fecha...")
        self.buril = TextInput(hint_text="Buril...")
        self.corte = TextInput(hint_text="Velocidad de corte...")

        for widget in [self.campo_nombre, self.operacion, self.material, self.fecha, self.buril, self.corte]:
            layout.add_widget(widget)

        boton = Button(text="Iniciar Monitoreo de Vibraciones", font_size='24sp', size_hint_y=None, height='60dp', background_color=(0.2, 0.7, 0.2, 1))
        boton.bind(on_press=self.go_to_graph_screen)
        layout.add_widget(boton)

        self.add_widget(layout)

    def update_bg_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def go_to_graph_screen(self, instance):
        self.manager.current = 'graph_screen'


class GraphScreen(Screen):
    _receive_thread = None
    _socket = None
    _is_running = False
    _sim_event = None
    _alert_shown = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.alert_count = 0
        self.plot_accel_x = MeshLinePlot(color=[1, 0, 0, 1])
        self.plot_accel_y = MeshLinePlot(color=[0, 1, 0, 1])
        self.plot_accel_z = MeshLinePlot(color=[0, 0, 1, 1])
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=40, spacing=10)
        with layout.canvas.before:
            self.bg_rect = Rectangle(source='fondo1.png', pos=layout.pos, size=layout.size)
        layout.bind(pos=self.update_bg_rect, size=self.update_bg_rect)

        layout.add_widget(Label(text="Monitoreo de Vibraciones en Tiempo Real", font_size='32sp', bold=True, color=(1, 1, 1, 1), size_hint_y=None, height='80dp'))

        self.graph = Graph(xlabel='Tiempo', ylabel='Aceleración (g)',
                           x_ticks_major=10, y_ticks_major=0.5,
                           xmin=0, xmax=MAX_POINTS, ymin=-2, ymax=2,
                           x_grid=True, y_grid=True,
                           background_color=(0, 0, 0, 0.5), border_color=(0.8, 0.8, 0.8, 1))

        self.graph.add_plot(self.plot_accel_x)
        self.graph.add_plot(self.plot_accel_y)
        self.graph.add_plot(self.plot_accel_z)
        layout.add_widget(self.graph)

        self.alert_counter_label = Label(text="Alertas detectadas: 0", font_size='20sp', color=(1, 1, 0, 1), size_hint_y=None, height='40dp')
        layout.add_widget(self.alert_counter_label)

        boton = Button(text="Volver", font_size='24sp', size_hint_y=None, height='60dp', background_color=(0.9, 0.2, 0.2, 1))
        boton.bind(on_press=self.stop_monitoring_and_go_back)
        layout.add_widget(boton)

        self.add_widget(layout)

    def update_bg_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def on_enter(self, *args):
        data_x_accel.clear()
        data_y_accel.clear()
        data_z_accel.clear()
        global current_time_point
        current_time_point = 0
        self.alert_count = 0
        self.update_alert_counter_label()
        self._alert_shown = False
        self.start_monitoring()

    def on_leave(self, *args):
        self.stop_monitoring()

    def start_monitoring(self):
        if self._is_running:
            return
        self._is_running = True

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((ESP32_IP, ESP32_PORT))
            self._socket.settimeout(1.0)
            self._receive_thread = threading.Thread(target=self._receive_data_from_esp32, daemon=True)
            self._receive_thread.start()
        except Exception as e:
            print(f"No se pudo conectar: {e}")
            self._socket = None
            self._sim_event = Clock.schedule_interval(self._simulate_data, 0.05)

        Clock.schedule_interval(self.update_graph, 0.1)

    def stop_monitoring(self):
        self._is_running = False
        Clock.unschedule(self.update_graph)
        if self._sim_event:
            Clock.unschedule(self._simulate_data)

        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self._socket.close()
            self._socket = None

        if self._receive_thread:
            self._receive_thread.join(timeout=1)

    def stop_monitoring_and_go_back(self, instance):
        self.stop_monitoring()
        self.manager.current = 'main_screen'

    def _receive_data_from_esp32(self):
        global current_time_point
        while self._is_running:
            try:
                data_raw = self._socket.recv(1024).decode('utf-8').strip()
                if data_raw:
                    accel_values = [float(val) for val in data_raw.split(',')]
                    if len(accel_values) == 3:
                        x, y, z = accel_values
                        data_x_accel.append((current_time_point, x))
                        data_y_accel.append((current_time_point, y))
                        data_z_accel.append((current_time_point, z))
                        current_time_point += 1
            except:
                continue

    def _simulate_data(self, dt):
        global current_time_point
        x = random.uniform(-2.0, 2.0)
        y = random.uniform(-2.0, 2.0)
        z = random.uniform(-9.5, -9.0)
        data_x_accel.append((current_time_point, x))
        data_y_accel.append((current_time_point, y))
        data_z_accel.append((current_time_point, z))
        current_time_point += 1

    def update_graph(self, dt):
        self.plot_accel_x.points = list(data_x_accel)
        self.plot_accel_y.points = list(data_y_accel)
        self.plot_accel_z.points = list(data_z_accel)

        if data_x_accel:
            self.graph.xmin = max(0, data_x_accel[0][0])
            self.graph.xmax = max(MAX_POINTS, data_x_accel[-1][0] + 1)

        self.check_for_dangerous_vibrations()

    def check_for_dangerous_vibrations(self):
        if self._alert_shown:
            return

        threshold_x = 1.5
        threshold_y = 1.5
        threshold_z = 2.5

        if data_x_accel and data_y_accel and data_z_accel:
            _, x = data_x_accel[-1]
            _, y = data_y_accel[-1]
            _, z = data_z_accel[-1]
            if abs(x) > threshold_x or abs(y) > threshold_y or abs(z + 9.8) > threshold_z:
                self._alert_shown = True
                self.alert_count += 1
                self.update_alert_counter_label()
                self.show_alert_popup("¡Alerta de Vibración Peligrosa!",
                                      "Se han detectado niveles de vibración elevados. Verifique el torno.")

    def update_alert_counter_label(self):
        self.alert_counter_label.text = f"Alertas detectadas: {self.alert_count}"

    def show_alert_popup(self, title, message):
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        label = Label(text=message, font_size='18sp', color=(1, 0, 0, 1))
        btn_continue = Button(text="Continuar", size_hint_y=None, height='40dp', background_color=(0, 0.7, 0, 1))
        btn_stop = Button(text="Detener medición", size_hint_y=None, height='40dp', background_color=(0.7, 0, 0, 1))
        layout.add_widget(label)
        layout.add_widget(btn_continue)
        layout.add_widget(btn_stop)
        popup = Popup(title=title, content=layout, size_hint=(0.8, 0.5))

        btn_continue.bind(on_press=lambda *a: (popup.dismiss(), self.reset_alert_flag()))
        btn_stop.bind(on_press=lambda *a: (popup.dismiss(), self.stop_and_show_summary()))

        popup.open()

    def reset_alert_flag(self):
        self._alert_shown = False

    def stop_and_show_summary(self):
        self.stop_monitoring()
        self._alert_shown = False
        self.manager.current = 'summary_screen'
        # Pasar datos a summary_screen
        summary_screen = self.manager.get_screen('summary_screen')
        main_screen = self.manager.get_screen('main_screen')
        summary_screen.set_summary(
            nombre=main_screen.campo_nombre.text,
            operacion=main_screen.operacion.text,
            material=main_screen.material.text,
            fecha=main_screen.fecha.text,
            buril=main_screen.buril.text,
            corte=main_screen.corte.text,
            alert_count=self.alert_count
        )


class SummaryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=40, spacing=10)

        with layout.canvas.before:
            self.bg_rect = Rectangle(source='fondo1.png', pos=layout.pos, size=layout.size)
        layout.bind(pos=self.update_bg_rect, size=self.update_bg_rect)

        self.label_title = Label(text="Resumen de Medición", font_size='32sp', bold=True, color=(1,1,1,1), size_hint_y=None, height='80dp')
        layout.add_widget(self.label_title)

        self.summary_label = Label(text="", font_size='20sp', color=(1,1,1,1))
        layout.add_widget(self.summary_label)

        # Botón para exportar el resumen a un archivo txt
        boton_exportar = Button(text="Exportar a TXT", font_size='24sp', size_hint_y=None, height='60dp', background_color=(0.2, 0.5, 0.9, 1))
        boton_exportar.bind(on_press=self.export_to_txt)
        layout.add_widget(boton_exportar)

        boton_volver = Button(text="Volver a Inicio", font_size='24sp', size_hint_y=None, height='60dp', background_color=(0.2, 0.7, 0.2, 1))
        boton_volver.bind(on_press=self.go_back_to_main)
        layout.add_widget(boton_volver)

        self.add_widget(layout)

    def update_bg_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def set_summary(self, nombre, operacion, material, fecha, buril, corte, alert_count):
        self.resumen_text = (
            f"Nombre: {nombre}\n"
            f"Operación: {operacion}\n"
            f"Material: {material}\n"
            f"Fecha: {fecha}\n"
            f"Buril: {buril}\n"
            f"Velocidad de corte: {corte}\n\n"
            f"Número de alertas: {alert_count}"
        )
        self.summary_label.text = self.resumen_text

    def export_to_txt(self, instance):
        try:
            with open("resumen_vibracion.txt", "w", encoding="utf-8") as f:
                f.write(self.resumen_text)
            popup = Popup(title="Exportación exitosa",
                          content=Label(text="Archivo resumen_vibracion.txt guardado correctamente."),
                          size_hint=(0.6, 0.4))
            popup.open()
        except Exception as e:
            popup = Popup(title="Error al exportar",
                          content=Label(text=f"No se pudo guardar el archivo:\n{e}"),
                          size_hint=(0.6, 0.4))
            popup.open()

    def go_back_to_main(self, instance):
        self.manager.current = 'main_screen'


class VibracionApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main_screen'))
        sm.add_widget(GraphScreen(name='graph_screen'))
        sm.add_widget(SummaryScreen(name='summary_screen'))
        return sm


if __name__ == '__main__':
    VibracionApp().run()