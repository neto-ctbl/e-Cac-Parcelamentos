# Automação e-CAC Parcelamentos — versão Playwright

Esta versão usa **Playwright + Google Chrome instalado** para consultar parcelamentos por CNPJ no e-CAC.

## O que consulta

Por CNPJ, nesta ordem:

1. PGFN / Regularize / SISPAR
2. Parcelamento Simples Nacional normal
3. PERT-SN
4. RELP-SN
5. Parcelamento Simplificado / SIEFPAR

## Importante sobre certificado e captcha

* O script usa o Chrome em modo visual (`HEADLESS=false`).
* Se o Windows/Chrome pedir seleção de certificado, selecione manualmente o certificado correto.
* hCaptcha não é burlado. Quando aparecer, o script pausa e você resolve manualmente.
* A consulta continua depois que você pressionar ENTER no terminal.

## Instalação

Abra o PowerShell na pasta do projeto e rode:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

Se for usar o Google Chrome instalado, normalmente o `BROWSER\_CHANNEL=chrome` já resolve. Caso queira usar o Chromium do Playwright, altere no `.env`:

```env
BROWSER\_CHANNEL=
```

Mas para certificado instalado na máquina, o Chrome instalado costuma ser a melhor opção.

## Configuração

1. Copie `.env.exemplo` para `.env`.
2. Ajuste `INPUT\_FILE` se necessário.
3. Preencha o `cnpjs.csv` com uma coluna chamada `CNPJ`.

Exemplo:

```csv
CNPJ
00.353.416/0001-93
07.939.334/0001-74
```

## Execução

```powershell
.\\.venv\\Scripts\\Activate.ps1
python main.py
```

## Saídas

Na pasta `saida` serão gerados:

* `parcelamentos\_ecac.xlsx`
* `parcelamentos\_ecac.json`
* `parcelamentos\_ecac\_parcial.xlsx`
* `parcelamentos\_ecac\_parcial.json`
* prints de erro, quando houver

## Observações de estabilidade

Portais do e-CAC, Regularize, SISPAR e SIEFPAR mudam bastante de tela e carregam muito conteúdo via JavaScript/Ajax. A primeira execução deve ser tratada como teste assistido para ajustar seletores finos quando necessário.

A automação já registra erros e salva resultado parcial após cada módulo, para não perder o progresso.
