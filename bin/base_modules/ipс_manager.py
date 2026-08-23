from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QObject
from config import socket_name
from log_config import logger

def activate_existing_window():
    """Пытается отправить команду существующему приложению"""
    try:
        socket = QLocalSocket()
        socket.connectToServer(socket_name)

        if socket.waitForConnected(2000):
            from PySide6.QtCore import QThread
            QThread.msleep(50)

            socket.write(b'show_window')

            if socket.waitForBytesWritten(1000):
                logger.info("[IPCManager] Команда отправлена существующему приложению")
            else:
                logger.error("[IPCManager] Данные не были отправлены")
                
            socket.disconnectFromServer()
            return True
        else:
            logger.error("[IPCManager] Не удалось подключиться к IPC серверу")
            return False
    except Exception as e:
        logger.error(f"[IPCManager] IPC client error: {e}")
        return False
    

class IPCManager(QObject):
    def __init__(self, main_window=None):
        super().__init__()
        self.main = main_window
        self.start_ipc_server()

    def start_ipc_server(self):
        """Настраивает IPC сервер используя Qt (без потоков)"""
        self.ipc_server = QLocalServer()
        self.ipc_server.newConnection.connect(self.handle_ipc_connection)

        QLocalServer.removeServer(socket_name)

        if not self.ipc_server.listen(socket_name):
            logger.error(f"[IPCManager][start_ipc_server] IPC server error: {self.ipc_server.errorString()}")
        else:
            logger.info("[MAIPCManagerIN][start_ipc_server] IPC server started")

    def handle_ipc_connection(self):
        """Обрабатывает входящие соединения"""
        socket = self.ipc_server.nextPendingConnection()
        logger.info(f"[IPCManager][handle_ipc_connection] New connection: {socket}")
        
        if socket:
            # Многократные попытки чтения
            for attempt in range(5):
                if socket.waitForReadyRead(100):  # Короткие интервалы
                    if socket.bytesAvailable() > 0:
                        data = socket.readAll().data()
                        logger.info(f"[IPCManager][handle_ipc_connection] IPC data received (attempt {attempt+1}): {data}")
                        if data == b'show_window':
                            logger.info("[IPCManager][handle_ipc_connection] Activating window...")
                            self.force_show_window()
                        break
                else:
                    logger.warning(f"[IPCManager][handle_ipc_connection] Attempt {attempt+1}: No data yet")
            
            socket.disconnectFromServer()
            socket.deleteLater()
            logger.info("[IPCManager] Connection closed")
            
    def read_ipc_data(self, socket):
        """Читает данные из IPC соединения"""
        try:
            if socket.bytesAvailable() > 0:
                data = socket.readAll().data()
                logger.debug(f"[IPCManager][read_ipc_data] IPC data received: {data}")
                if data == b'show_window':
                    self.force_show_window()
            
            # Всегда закрываем соединение после чтения
            socket.disconnectFromServer()
            socket.deleteLater()
            
        except Exception as e:
            logger.error(f"[IPCManager][read_ipc_data] Error reading IPC data: {e}")

    def force_show_window(self):
        """Принудительное открытие окна из любого состояния"""
        logger.debug(f"[IPCManager][force_show_window] called. isVisible: {self.main.isVisible()}, isMinimized: {self.main.isMinimized()}, isHidden: {self.main.isHidden()}")
        
        # Всегда показываем окно
        self.main.show()
        self.main.showNormal()
        
        # Активация и фокус
        self.main.activateWindow()
        self.main.raise_()
        self.main.setFocus()
        
        # Центрирование
        screen_geometry = self.main.screen().availableGeometry()
        self.main.move(
            (screen_geometry.width() - self.main.width()) // 2,
            (screen_geometry.height() - self.main.height()) // 2
        )

        self.main.update()
        self.main.repaint()
        self.main.logs_widget.log_area.start_active_mode()
        
        logger.debug(f"[IPCManager][force_show_window] After force_show: isVisible: {self.main.isVisible()}, isMinimized: {self.main.isMinimized()}")