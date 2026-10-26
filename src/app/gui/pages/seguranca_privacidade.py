from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SegurancaPrivacidadeWidget(QWidget):
    """Área informativa de Segurança e Privacidade do Finance."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("Segurança e Privacidade")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        description = QLabel(
            "Informações sobre acesso, proteção da conta "
            "e utilização responsável dos dados financeiros."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        sections = (
            (
                "Proteção da conta",
                "Utilize uma senha forte e pessoal. "
                "A alteração de senha está disponível na área Minha Conta.",
            ),
            (
                "Controle de acesso",
                "O Finance utiliza perfis e permissões para controlar "
                "o acesso às funcionalidades administrativas.",
            ),
            (
                "Privacidade dos dados",
                "Os dados financeiros devem ser acessados e utilizados "
                "somente por pessoas autorizadas.",
            ),
            (
                "Administração e auditoria",
                "As funcionalidades de gestão de usuários e consulta "
                "de auditoria dependem das permissões do perfil.",
            ),
        )

        self.cards = []

        for heading, content in sections:
            card = QFrame()
            card.setObjectName("securityPrivacyCard")
            card.setStyleSheet(
                "QFrame#securityPrivacyCard {"
                "background: #ffffff;"
                "border: 1px solid #d6dee8;"
                "border-radius: 10px;"
                "}"
                "QFrame#securityPrivacyCard QLabel {"
                "border: none;"
                "background: transparent;"
                "}"
            )

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 14, 18, 14)
            card_layout.setSpacing(6)

            heading_label = QLabel(heading)
            heading_label.setObjectName("sectionTitle")

            content_label = QLabel(content)
            content_label.setWordWrap(True)
            content_label.setStyleSheet("color: #4A5568;")

            card_layout.addWidget(heading_label)
            card_layout.addWidget(content_label)

            card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )

            layout.addWidget(card)
            self.cards.append(card)

        layout.addStretch()