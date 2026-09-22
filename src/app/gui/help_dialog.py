from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QTextBrowser, QVBoxLayout,
)

SUPPORT_WHATSAPP_DISPLAY = "(62) 9 8167-2265"
SUPPORT_WHATSAPP_NUMBER = "5562981672265"

TOPICS = {
    "Como usar o Finance": "O Finance centraliza as rotinas financeiras, de BOE, metas, cadastros e relatórios. Use a navegação lateral para acessar os módulos liberados para o seu perfil.",
    "Dashboard": "Apresenta os indicadores permitidos ao seu perfil. Utilize os filtros disponíveis para consultar o período desejado e Atualizar para recarregar os dados.",
    "Financeiro": "Permite consultar o fluxo financeiro. Perfis autorizados também podem incluir lançamentos e realizar as importações disponíveis.",
    "BOE": "Permite consultar os dados de BOE e, quando autorizado, executar as operações disponíveis no módulo.",
    "Orçado x Realizado": "Compara valores orçados e realizados conforme o período e os filtros disponíveis.",
    "Metas e Ranking": "O módulo Metas permite acompanhar metas e realizados. A área Ranking e Premiação apresenta a classificação calculada conforme os parâmetros do ano.",
    "Cadastros": "Reúne a Base Mestre de Entidades e o Catálogo do Fluxo de Caixa. As áreas e ações visíveis dependem das permissões do usuário.",
    "Relatórios": "Permite consultar relatórios e, para perfis autorizados, exportar os dados disponíveis.",
    "Administração": "Reúne Minha conta e, conforme o perfil, recursos administrativos, usuários, auditoria e parâmetros do Ranking.",
    "Recuperação de senha": "Na tela de entrada, use Esqueci minha senha. Se possuir sua chave pessoal, informe-a para redefinir a senha. Sem a chave, utilize Recuperação assistida e envie o código ao suporte pelo WhatsApp (62) 9 8167-2265.",
    "Perguntas Frequentes": "Se uma opção não estiver visível, ela pode não estar liberada para o seu perfil. Em caso de dúvida operacional ou necessidade de recuperação assistida, fale com o suporte.",
}


class HelpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Finance — Central de Ajuda")
        self.setModal(True)
        self.resize(840, 650)
        self.setMinimumSize(720, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Central de Ajuda do Finance")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        intro = QLabel(f"Precisa de atendimento? Use o suporte oficial pelo WhatsApp {SUPPORT_WHATSAPP_DISPLAY}.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar orientação")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        content = QHBoxLayout()
        self.topics = QListWidget()
        self.topics.setMinimumWidth(245)
        self.topics.currentTextChanged.connect(self._show_topic)
        content.addWidget(self.topics, 1)

        self.text = QTextBrowser()
        content.addWidget(self.text, 2)
        layout.addLayout(content, 1)

        self.whatsapp = QPushButton("Falar com o suporte pelo WhatsApp")
        self.whatsapp.setProperty("buttonRole", "primary")
        self.whatsapp.clicked.connect(self._open_whatsapp)
        layout.addWidget(self.whatsapp)
        self._filter("")

    def _filter(self, value: str) -> None:
        query = value.strip().casefold()
        current = self.topics.currentItem().text() if self.topics.currentItem() else ""
        self.topics.clear()
        for title, body in TOPICS.items():
            if not query or query in title.casefold() or query in body.casefold():
                self.topics.addItem(title)
        matches = self.topics.findItems(current, Qt.MatchFlag.MatchExactly)
        if matches:
            self.topics.setCurrentItem(matches[0])
        elif self.topics.count():
            self.topics.setCurrentRow(0)
        else:
            self.text.setPlainText("Nenhuma orientação encontrada para a busca informada.")

    def _show_topic(self, title: str) -> None:
        if title:
            self.text.setHtml(f"<h3>{title}</h3><p>{TOPICS[title]}</p>")

    def _open_whatsapp(self) -> None:
        message = "Olá. Preciso de ajuda com o Finance da J.A. Technology."
        encoded = bytes(QUrl.toPercentEncoding(message)).decode("ascii")
        QDesktopServices.openUrl(QUrl(f"https://wa.me/{SUPPORT_WHATSAPP_NUMBER}?text={encoded}"))
