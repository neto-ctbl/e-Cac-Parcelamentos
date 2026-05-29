# Consulta de Parcelamentos e-CAC / PGFN / SIEFPAR

Automação em Python + Selenium para consultar parcelamentos de empresas usando o certificado digital já instalado na máquina.

## O que consulta

Por CNPJ, o fluxo roda nesta ordem:

1. Altera o perfil de acesso no e-CAC para o CNPJ da empresa.
2. Consulta PGFN / Regularize / SISPAR.
3. Consulta Parcelamento Simples Nacional normal.
4. Consulta PERT-SN.
5. Consulta RELP-SN.
6. Consulta Parcelamento Simplificado / SIEFPAR.

## Saídas geradas

Na pasta `saida/`:

- `parcelamentos_ecac.xlsx`
- `parcelamentos_ecac.json`
- `parcelamentos_ecac_parcial.xlsx`
- `parcelamentos_ecac_parcial.json`
- prints de erro, quando houver

O Excel possui três abas:

- `Parcelamentos`
- `Debitos Parcelados`
- `Erros`

## Instalação

No Prompt de Comando/PowerShell, dentro da pasta do projeto:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Entrada de CNPJs

Edite o arquivo `cnpjs.csv`:

```csv
CNPJ
00353416000193
07939334000174
22633997000150
```

O script completa zeros à esquerda e remove máscara automaticamente.

Também aceita `.xlsx`, desde que haja uma coluna chamada `CNPJ` ou que a primeira coluna contenha os CNPJs.

Para usar outro arquivo, edite `config.py` ou crie `.env` com:

```env
INPUT_CSV=G:\CAMINHO\empresas.csv
```

## Chrome / certificado digital

Por padrão, o script abre um Chrome novo via Selenium.

Se quiser usar o mesmo perfil do Chrome que já tem certificado/configurações, copie `.env.exemplo` para `.env` e preencha:

```env
CHROME_USER_DATA_DIR=C:\Users\SEU_USUARIO\AppData\Local\Google\Chrome\User Data
CHROME_PROFILE_DIR=Default
```

Atenção: feche outras janelas do Chrome antes de usar o mesmo perfil, para evitar conflito.

## Execução

```bash
python main.py
```

Durante a execução:

- Se aparecer a janela de escolha do certificado, selecione o certificado correto e pressione ENTER no terminal.
- Nos hCaptchas do Simples/Pert/Relp, resolva manualmente no navegador e pressione ENTER no terminal.

## Regras de consulta implementadas

### Simples Nacional, PERT-SN e RELP-SN

- Detecta popup de ausência de pedido:
  - `Não existe pedido de parcelamento para esse CNPJ.`
  - `Não existe pedido de parcelamento PERT-SN para esse CNPJ.`
  - `Não existe pedido de parcelamento RELP-SN para esse CNPJ.`
- Lê pedidos com situação `Em parcelamento`.
- Lê consolidação, demonstrativo de pagamentos e extrato da última parcela.
- Calcula parcela atual pela última competência paga + diferença até a competência atual.

Exemplo:

- Última competência paga: `03/2026`
- Nº do parcelamento/Nº da parcela: `9131/47`
- Competência atual: `05/2026`
- Parcela atual estimada: `49`

### Parcelamento Simplificado / SIEFPAR

- Detecta ausência de negociação pela mensagem:
  - `Não existem negociações com os critérios informados.`
- Consulta negociações ativas.
- Lê extrato da negociação.
- Lê demonstrativo de parcelas.
- Define a parcela atual como a primeira parcela com situação diferente de `Paga`.
- Define atraso se houver parcela devedora ou parcela vencida não paga.

### PGFN / Regularize / SISPAR

- Abre o Regularize em nova aba.
- Se cair na tela de cadastro do Regularize, registra como sem parcelamento PGFN.
- Caso entre no SISPAR, tenta navegar até emissão/documento e extrair dados do resumo.

## Observação importante

Esta é a primeira versão funcional/base. Portais do governo mudam seletores, carregam partes por Ajax e podem variar conforme o tipo de débito/parcelamento. Por isso o script salva relatório parcial após cada módulo e tira print quando encontra erro.
