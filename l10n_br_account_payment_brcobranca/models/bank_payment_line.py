# Copyright 2020 Akretion
# @author Magno Costa <magno.costa@akretion.com.br>
# Copyright 2020 KMEE
# @author Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models, api, fields, _

_logger = logging.getLogger(__name__)

try:
    from erpbrasil.base import misc
except ImportError:
    _logger.error("Biblioteca erpbrasil.base não instalada")


class BankPaymentLine(models.Model):
    _inherit = "bank.payment.line"

    def _prepare_bank_line_vals(self):
        return {
            'valor': self.amount_currency,
            'data_vencimento': self.date.strftime('%Y/%m/%d'),
            'nosso_numero': self.own_number,
            'documento_sacado': misc.punctuation_rm(self.partner_id.cnpj_cpf),
            'nome_sacado':
                self.partner_id.legal_name.strip()[:40],
            'numero': str(self.document_number)[:10],
            'endereco_sacado': str(
                self.partner_id.street + ', ' + str(
                    self.partner_id.street_number))[:40],
            'bairro_sacado':
                self.partner_id.district.strip(),
            'cep_sacado': misc.punctuation_rm(self.partner_id.zip),
            'cidade_sacado':
                self.partner_id.city_id.name,
            'uf_sacado': self.partner_id.state_id.code,
            'identificacao_ocorrencia': self.order_id.movement_instruction_code
        }

    def _prepare_bank_line_unicred(self, payment_mode_id, linhas_pagamentos):
        # TODO - Verificar se é uma tabela unica por banco ou há padrão
        # Identificação da Ocorrência:
        # 01 - Remessa*
        # 02 - Pedido de Baixa
        # 04 - Concessão de Abatimento*
        # 05 - Cancelamento de Abatimento
        # 06 - Alteração de vencimento
        # 08 - Alteração de Seu Número
        # 09 - Protestar*
        # 11 - Sustar Protesto e Manter em Carteira
        # 25 - Sustar Protesto e Baixar Título
        # 26 – Protesto automático
        # 31 - Alteração de outros dados (Alteração de dados do pagador)
        # 40 - Alteração de Carteira
        linhas_pagamentos['identificacao_ocorrencia'] = '01'
        linhas_pagamentos['codigo_protesto'] = \
            payment_mode_id.boleto_protest_code or '3'
        linhas_pagamentos['dias_protesto'] = \
            payment_mode_id.boleto_days_protest or '0'

        # Código adotado pela FEBRABAN para identificação
        # do tipo de pagamento de multa.
        # Domínio:
        # ‘1’ = Valor Fixo (R$)
        # ‘2’ = Taxa (%)
        # ‘3’ = Isento
        # Isento de Multa caso não exista percentual
        linhas_pagamentos['codigo_multa'] = '3'

        # Isento de Mora
        linhas_pagamentos['tipo_mora'] = '5'

        # TODO
        # Código adotado pela FEBRABAN para identificação do desconto.
        # Domínio:
        # 0 = Isento
        # 1 = Valor Fixo
        linhas_pagamentos['cod_desconto'] = '0'
        # 00000005/01
        linhas_pagamentos['numero'] = str(self.document_number)[1:11]

        if payment_mode_id.boleto_discount_perc:
            linhas_pagamentos['cod_desconto'] = '1'

    def prepare_bank_payment_line(self, bank_name_brcobranca):
        payment_mode_id = self.order_id.payment_mode_id
        linhas_pagamentos = self._prepare_bank_line_vals()
        try:
            bank_method = getattr(
                self, '_prepare_bank_line_{}'.format(bank_name_brcobranca.name)
            )
            if bank_method:
                bank_method(payment_mode_id, linhas_pagamentos)
        except:
            pass

        if payment_mode_id.boleto_fee_perc:
            linhas_pagamentos['codigo_multa'] = \
                payment_mode_id.boleto_fee_code
            linhas_pagamentos['percentual_multa'] = \
                payment_mode_id.boleto_fee_perc

        precision = self.env['decimal.precision']
        precision_account = precision.precision_get('Account')
        if payment_mode_id.boleto_interest_perc:
            linhas_pagamentos['tipo_mora'] = \
                payment_mode_id.boleto_interest_perc
            # TODO - É padrão em todos os bancos ?
            # Código adotado pela FEBRABAN para identificação do tipo de
            # pagamento de mora de juros.
            # Domínio:
            # ‘1’ = Valor Diário (R$)
            # ‘2’ = Taxa Mensal (%)
            # ‘3’= Valor Mensal (R$) *
            # ‘4’ = Taxa diária (%)
            # ‘5’ = Isento
            # *OBSERVAÇÃO:
            # ‘3’ - Valor Mensal (R$): a CIP não acata valor mensal,
            # segundo manual. Cógido mantido
            # para Correspondentes que ainda utilizam.
            # Isento de Mora caso não exista percentual
            if payment_mode_id.boleto_interest_code == '1':
                linhas_pagamentos['valor_mora'] = round(
                    self.amount_currency *
                    ((payment_mode_id.boleto_interest_code / 100)
                     / 30), precision_account)
            if payment_mode_id.boleto_interest_code == '2':
                linhas_pagamentos['valor_mora'] = \
                    payment_mode_id.boleto_interest_code

        if payment_mode_id.boleto_discount_perc:
            linhas_pagamentos['data_desconto'] = \
                self.date.strftime('%Y/%m/%d')
            linhas_pagamentos['valor_desconto'] = round(
                self.amount_currency * (
                        payment_mode_id.boleto_discount_perc / 100),
                precision_account)

        # Protesto
        if payment_mode_id.boleto_protest_code:
            linhas_pagamentos['codigo_protesto'] = \
                payment_mode_id.boleto_protest_code
            if payment_mode_id.boleto_days_protest:
                linhas_pagamentos['dias_protesto'] = \
                    payment_mode_id.boleto_days_protest
        return linhas_pagamentos
