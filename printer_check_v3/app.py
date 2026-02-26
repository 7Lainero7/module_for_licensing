import sys
import os
import tempfile
import win32print
import win32ui
from PIL import Image, ImageWin
import treepoem
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from license_manager import LicenseManager

def setup_ghostscript():
    """Простая проверка Ghostscript"""
    import shutil
    gs_path = shutil.which('gswin64c.exe') or shutil.which('gswin32c.exe')
    if gs_path:
        os.environ["GS"] = gs_path
        print(f"Using Ghostscript: {gs_path}")
        return True
    else:
        print("Ghostscript not found in PATH")
        return False

# Настраиваем Ghostscript при запуске
if not setup_ghostscript():
    print("ERROR: Ghostscript setup failed")

printed_codes = set()

def parse_gs1_string(raw: str):
    """
    Жёсткий парсер под формат Честного ЗНАКа:
    (01)14 цифр + (21)до 20 символов + (91) + (92)
    """
    ai_list = []
    if raw.startswith("01"):
        gtin = raw[2:16]
        ai_list.append(("01", gtin))
        pos = 16
    else:
        return []

    if raw[pos:pos+2] == "21":
        pos += 2
        # серийник идёт до "91"
        next_ai = raw.find("91", pos)
        if next_ai == -1:
            return []  # Не нашли 91
        serial = raw[pos:next_ai]
        ai_list.append(("21", serial))
        pos = next_ai
    
    if raw[pos:pos+2] == "91":
        pos += 2
        if len(raw) >= pos + 4:
            val91 = raw[pos:pos+4]
            ai_list.append(("91", val91))
            pos += 4
        else:
            return []
    
    if pos < len(raw) and raw[pos:pos+2] == "92":
        pos += 2
        val92 = raw[pos:]
        ai_list.append(("92", val92))

    return ai_list

def generate_gs1dm(ai_list, out_file, scale_factor=1.0):
    """Принудительное задание размера"""
    data = "".join(f"({ai}){val}" for ai, val in ai_list)
    
    # Минимальный и максимальный размер в пикселях
    min_size = 200
    max_size = 1500
    target_size = int(min_size + (max_size - min_size) * (scale_factor - 0.5) / 3.5)
    target_size = max(min_size, min(max_size, target_size))
    
    # Генерируем с максимальным качеством
    img = treepoem.generate_barcode(
        barcode_type="gs1datamatrix", 
        data=data,
        scale=10  # Максимально возможный
    )
    
    # Принудительно масштабируем до целевого размера
    if img.width < target_size:
        # Увеличиваем
        img_resized = img.resize((target_size, target_size), Image.NEAREST)
    else:
        # Уменьшаем если нужно
        img_resized = img.resize((target_size, target_size), Image.LANCZOS)
    
    # Создаем изображение с белым фоном и отступами
    padding = 20
    final_size = target_size + 2 * padding
    final_img = Image.new('RGB', (final_size, final_size), 'white')
    final_img.paste(img_resized, (padding, padding))
    
    final_img.save(out_file, dpi=(300, 300))
    return out_file

def print_image_centered(printer_name, file_path, scale_factor=1.0):
    """Печать с принудительным контролем размера"""
    try:
        HORZRES = 8
        VERTRES = 10
        
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        
        try:
            printable_width = hdc.GetDeviceCaps(HORZRES)
            printable_height = hdc.GetDeviceCaps(VERTRES)
            
            bmp = Image.open(file_path)
            
            # Принудительно задаем размер относительно масштаба
            base_target_ratio = 0.5  # 50% страницы по умолчанию
            target_ratio = base_target_ratio * scale_factor
            
            target_width = int(printable_width * target_ratio)
            target_height = int(printable_height * target_ratio)
            
            # Масштабируем
            ratio = min(target_width / bmp.size[0], target_height / bmp.size[1])
            new_size = (int(bmp.size[0] * ratio), int(bmp.size[1] * ratio))
            
            # Центрируем
            x = (printable_width - new_size[0]) // 2
            y = (printable_height - new_size[1]) // 2
            
            hdc.StartDoc("GS1 DataMatrix")
            hdc.StartPage()
            
            resized_bmp = bmp.resize(new_size, Image.NEAREST)  # NEAREST для четкости
            dib = ImageWin.Dib(resized_bmp)
            dib.draw(hdc.GetHandleOutput(), (x, y, x + new_size[0], y + new_size[1]))
            
            hdc.EndPage()
            hdc.EndDoc()
            
        finally:
            hdc.DeleteDC()
            
    except Exception as e:
        print(f"Ошибка печати: {str(e)}")
        raise

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QtCore.QSettings("GS1Printer", "DataMatrixPrinter")
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        self.setWindowTitle("GS1 DataMatrix Printer")
        self.setFixedSize(500, 600)  # Увеличил высоту для новых кнопок

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Группа настроек
        settings_group = QtWidgets.QGroupBox("Настройки печати")
        settings_layout = QtWidgets.QGridLayout()
        
        # Выбор принтера
        settings_layout.addWidget(QtWidgets.QLabel("Принтер:"), 0, 0)
        self.printer_combo = QtWidgets.QComboBox()
        printers = [p[2] for p in win32print.EnumPrinters(2)]
        self.printer_combo.addItems(printers)
        settings_layout.addWidget(self.printer_combo, 0, 1)
        
        # Кнопка обновления списка принтеров
        self.refresh_btn = QtWidgets.QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.find_printers)
        self.refresh_btn.setFixedHeight(30)
        settings_layout.addWidget(self.refresh_btn, 0, 2)
        
        # Масштаб - ползунок и спинбокс
        settings_layout.addWidget(QtWidgets.QLabel("Масштаб кода:"), 1, 0)
        
        # Горизонтальный layout для ползунка и спинбокса
        scale_layout = QtWidgets.QHBoxLayout()
        
        # Ползунок
        self.scale_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.scale_slider.setRange(50, 400)  # Увеличил диапазон до 400%
        self.scale_slider.setValue(100)
        self.scale_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.scale_slider.setTickInterval(50)
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        scale_layout.addWidget(self.scale_slider)
        
        # Спинбокс
        self.scale_spin = QtWidgets.QSpinBox()
        self.scale_spin.setRange(50, 400)
        self.scale_spin.setValue(100)
        self.scale_spin.setSuffix("%")
        self.scale_spin.valueChanged.connect(self.on_scale_spin_changed)
        self.scale_spin.setFixedWidth(70)
        scale_layout.addWidget(self.scale_spin)
        
        settings_layout.addLayout(scale_layout, 1, 1, 1, 2)
        
        # Кнопки управления
        buttons_layout = QtWidgets.QHBoxLayout()
        
        # Кнопка тестовой печати
        # self.test_print_btn = QtWidgets.QPushButton("Тестовая печать")
        # self.test_print_btn.clicked.connect(self.test_print_gs1)
        # self.test_print_btn.setFixedHeight(35)
        # buttons_layout.addWidget(self.test_print_btn)
        
        # Кнопка сброса списка кодов
        self.reset_codes_btn = QtWidgets.QPushButton("Сброс кодов")
        self.reset_codes_btn.clicked.connect(self.reset_printed_codes)
        self.reset_codes_btn.setFixedHeight(35)
        self.reset_codes_btn.setStyleSheet("QPushButton { background-color: #ffcccc; }")
        buttons_layout.addWidget(self.reset_codes_btn)
        
        settings_layout.addLayout(buttons_layout, 2, 0, 1, 3)
        
        settings_group.setLayout(settings_layout)
        
        # Группа сканирования
        scan_group = QtWidgets.QGroupBox("Сканирование")
        scan_layout = QtWidgets.QVBoxLayout()
        
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("Отсканируйте DataMatrix код...")
        self.input_field.textChanged.connect(self.on_text_changed)
        self.input_field.setFixedHeight(35)
        font = self.input_field.font()
        font.setPointSize(11)
        self.input_field.setFont(font)
        
        scan_layout.addWidget(self.input_field)
        scan_group.setLayout(scan_layout)
        
        # Статус
        self.status_label = QtWidgets.QLabel("Готов к сканированию")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("background-color: #e0e0e0; padding: 8px; border-radius: 4px;")
        self.status_label.setFixedHeight(40)
        
        # Информация о напечатанных кодах
        self.codes_info = QtWidgets.QLabel("Напечатано кодов: 0")
        self.codes_info.setAlignment(QtCore.Qt.AlignCenter)
        self.codes_info.setStyleSheet("background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        
        # Лог
        log_group = QtWidgets.QGroupBox("Лог")
        log_layout = QtWidgets.QVBoxLayout()
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        # Добавляем все в layout
        layout.addWidget(settings_group)
        layout.addWidget(scan_group)
        layout.addWidget(self.status_label)
        layout.addWidget(self.codes_info)
        layout.addWidget(log_group)
        
        # Таймеры
        self.scan_timer = QtCore.QTimer()
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self.handle_scan)
        
        self.focus_timer = QtCore.QTimer()
        self.focus_timer.timeout.connect(self.ensure_focus)
        self.focus_timer.start(500)
        
        self.input_field.setFocus()
        self.update_codes_info()
        
    def load_settings(self):
        """Загрузка сохраненных настроек"""
        scale_value = self.settings.value("scale", 100, type=int)
        self.scale_slider.setValue(scale_value)
        self.scale_spin.setValue(scale_value)
    
    def save_settings(self):
        """Сохранение настроек"""
        self.settings.setValue("scale", self.scale_slider.value())
    
    def on_scale_changed(self, value):
        """Обработчик изменения ползунка масштаба"""
        self.scale_spin.setValue(value)
        self.save_settings()
    
    def on_scale_spin_changed(self, value):
        """Обработчик изменения спинбокса масштаба"""
        self.scale_slider.setValue(value)
        self.save_settings()
    
    def find_printers(self):
        """Обновление списка принтеров"""
        self.printer_combo.clear()
        try:
            printers = [p[2] for p in win32print.EnumPrinters(2)]
            self.printer_combo.addItems(printers)
            self.log_message(f"Обновлен список принтеров: {len(printers)} найдено")
        except Exception as e:
            self.log_message(f"Ошибка обновления принтеров: {str(e)}")
        
    def test_print_gs1(self):
        """Тестовая печать GS1 DataMatrix с валидными данными"""
        # Правильный формат GS1 DataMatrix для treepoem
        test_data = "010460123456789721TEST_SERIAL_00000191EE1192TEST_DATA_FOR_PRINTER_CHECK"
        self.process_dm_code(test_data, is_test=True)
    
    def reset_printed_codes(self):
        """Сброс списка напечатанных кодов"""
        count_before = len(printed_codes)
        printed_codes.clear()
        self.update_codes_info()
        self.log_message(f"Сброшен список напечатанных кодов. Удалено: {count_before} кодов")
        self.show_status("✅ Список кодов сброшен", 3000)
    
    def update_codes_info(self):
        """Обновление информации о количестве напечатанных кодов"""
        count = len(printed_codes)
        self.codes_info.setText(f"Напечатано кодов: {count}")
    
    def on_text_changed(self, text):
        """Обработчик изменения текста"""
        self.scan_timer.stop()
        if text.strip():
            self.scan_timer.start(300)
    
    def ensure_focus(self):
        """Обеспечение фокуса на поле ввода"""
        if not self.input_field.hasFocus():
            self.input_field.setFocus()
    
    def show_status(self, text, timeout=5000):
        """Показать статус"""
        self.status_label.setText(text)
        if not text.startswith("❌"):
            QtCore.QTimer.singleShot(timeout, lambda: self.status_label.setText("Готов к сканированию"))
    
    def log_message(self, text):
        """Добавить сообщение в лог"""
        self.log_text.append(f"{QtCore.QDateTime.currentDateTime().toString('hh:mm:ss')} - {text}")
        # Автопрокрутка вниз
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def handle_scan(self):
        """Обработка сканирования"""
        raw = self.input_field.text().strip()
        self.input_field.clear()
        
        if not raw:
            return

        if raw in printed_codes:
            self.show_status("⚠️ Дубликат - не печатаем")
            self.log_message("Обнаружен дубликат кода")
            return

        self.process_dm_code(raw)
    
    def process_dm_code(self, data, is_test=False):
        """Обработка и печать DataMatrix кода"""
        if not data:
            return False
        
        if self.printer_combo.count() == 0:
            self.show_status("❌ Ошибка: Принтеры не найдены!")
            return False
        
        printer_name = self.printer_combo.currentText()
        
        try:
            # Парсим GS1 строку
            ai_list = parse_gs1_string(data)
            if not ai_list:
                self.show_status("❌ Ошибка разбора GS1 строки")
                self.log_message(f"Неверный формат GS1: {data}")
                return False
            
            self.log_message(f"Разобрана GS1 строка: {ai_list}")
            
            # Генерируем временный файл
            tmpfile = os.path.join(tempfile.gettempdir(), f"gs1dm_{os.getpid()}.png")
            
            # Получаем настройки масштаба
            scale_factor = self.scale_slider.value() / 100.0
            
            # Генерируем DataMatrix
            try:
                generate_gs1dm(ai_list, tmpfile, scale_factor)
                self.log_message(f"DataMatrix сгенерирован успешно, масштаб: {scale_factor}")
            except Exception as e:
                self.show_status("❌ Ошибка генерации кода")
                self.log_message(f"Ошибка генерации: {str(e)}")
                return False
            
            # Печатаем
            try:
                print_image_centered(printer_name, tmpfile, scale_factor)
                
                printed_codes.add(data)
                self.update_codes_info()
                
                status_text = "✅ Тестовая печать успешна!" if is_test else "✅ Код напечатан"
                self.show_status(status_text)
                self.log_message("Успешно напечатано")
                
                return True
                
            except Exception as e:
                self.show_status("❌ Ошибка печати")
                self.log_message(f"Ошибка печати: {str(e)}")
                return False
                
        except Exception as e:
            self.show_status("❌ Ошибка обработки")
            self.log_message(f"Общая ошибка: {str(e)}")
            return False

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # ==========================================
    # БЛОК ПРОВЕРКИ ЛИЦЕНЗИИ
    # ==========================================
    license_mgr = LicenseManager()
    is_valid = False
    
    # 1. Пробуем локальную проверку
    is_valid, msg = license_mgr.check_local_license()
    
    # 2. Если не прошло, просим ключ
    if not is_valid:
        text, ok = QtWidgets.QInputDialog.getText(
            None, 
            "Активация программы", 
            f"{msg}\n\nВведите ключ активации:",
            QtWidgets.QLineEdit.Normal, 
            ""
        )
        
        if ok and text:
            # Пытаемся активировать онлайн
            is_valid, msg = license_mgr.check_online(text)
            if not is_valid:
                # Если ошибка активации
                QtWidgets.QMessageBox.critical(None, "Ошибка", msg)
                sys.exit(1)
        else:
            # Нажал отмену
            sys.exit(1)
            
    # Если лицензия валидна (либо локально, либо только что активирована)
    if not is_valid:
        # На всякий случай, если логика сломалась
        sys.exit(1)

    # ==========================================
    # ДАЛЬШЕ ИДЕТ ОБЫЧНЫЙ КОД ЗАПУСКА
    # ==========================================
    
    # Проверяем Ghostscript
    if not setup_ghostscript():
        # ... твой код ошибки GS ...
        sys.exit(1)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())