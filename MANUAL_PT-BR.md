# VCF Processor Fast - Manual do Usuário

## O que é este programa?

O **VCF Processor Fast** processa listas de contatos exportadas do WhatsApp (arquivos `.vcf`) ou listas de texto, remove duplicatas com base em um histórico de números já processados, e exporta o resultado para uma planilha Excel (`.xlsx`).

---

## Instalação

1. Baixe o arquivo `VCF_Processor_Installer.exe`
2. Execute o instalador — ele extrairá o programa automaticamente para `%LOCALAPPDATA%\VCF_Processor_Fast\`
3. Um atalho será criado na Área de Trabalho e no Menu Iniciar
4. Abra o programa pelo atalho **VCF Processor Fast**

---

## Interface Principal

Ao abrir o programa, você verá duas abas de modo de entrada:

- **Processar Arquivo VCF** — para arquivos `.vcf` exportados do WhatsApp
- **Processar Lista de Texto** — para colar texto copiado diretamente

### Formato de Saída Excel

Antes de processar, escolha o formato da planilha:

**Padrão** — gera duas colunas:
- `Number` — número de telefone
- `Name` — primeiro nome do contato

**Novo Programa** — gera quatro colunas:
- `Primeiro nome` — primeiro nome do contato
- `Sobrenome` — nome de quem enviou (campo "Quem Enviou")
- `Telefone` — número de telefone
- `Etiquetas` — mesmo valor de "Quem Enviou"

> Ao selecionar **Novo Programa**, aparece o campo **Quem Enviou** onde você digita o nome do remetente.

---

## Como Processar um Arquivo VCF

1. Clique na aba **Processar Arquivo VCF**
2. Clique em **Procurar** e selecione um ou mais arquivos `.vcf`
   - Você também pode **arrastar e soltar** os arquivos diretamente na janela
3. Clique em **Processar VCF**
4. Se não houver duplicatas, o arquivo Excel é gerado automaticamente na mesma pasta do VCF
5. Se houver duplicatas, o **Seletor de Duplicatas** aparece

---

## Como Processar uma Lista de Texto

1. Clique na aba **Processar Lista de Texto**
2. Cole o texto na área de texto. Formatos aceitos:
   - `[OK] Nome +5584999... foi adicionado com sucesso [OK]`
   - `Name: Nome... Number (1): +5584999...`
3. Clique em **Processar Texto**
4. O resultado segue o mesmo fluxo do VCF

---

## Seletor de Duplicatas

Quando o programa encontra contatos que já foram processados anteriormente, ele exibe a lista de duplicatas para você decidir o que fazer.

### Opções disponíveis:

- **Marcar individualmente** — clique na caixa ao lado do nome para selecionar
- **Selecionar todos** — marque a caixa "Selecionar todos" no topo da lista para selecionar todos os contatos, mesmo os que estão fora da área visível
- **Arrastar para selecionar** — clique e arraste sobre os nomes para selecionar vários de uma vez
- **Buscar** — use o campo de busca para filtrar por nome ou número

### Botões:

- **Processar** — processa os contatos selecionados (remove do histórico e adiciona ao Excel)
- **Pular** — ignora todas as duplicatas e processa apenas os contatos novos

---

## Processamento em Lote (Múltiplos VCFs)

Para processar vários arquivos VCF de uma vez:

1. Clique em **Procurar** e selecione múltiplos arquivos `.vcf` (segure Ctrl para selecionar vários)
2. Ou arraste vários arquivos de uma vez para a janela
3. Clique em **Processar Arquivos**
4. O programa combina todos os arquivos e processa como se fosse um único VCF

---

## Painel de Configurações

Clique no ícone de engrenagem (⚙) no canto superior esquerdo ou na aba lateral para abrir as configurações.

### Efeitos de Luz
Liga/desliga o efeito de sombra dinâmica que segue o cursor do mouse.

### Títulos Filtrados
Lista de palavras que são removidas automaticamente dos nomes dos contatos (ex: Dr, Prof, Sr, Eng).

- **Adicionar**: digite na caixa de texto e pressione Enter ou clique em **+**
- **Remover**: clique no **×** ao lado do título
- Separe múltiplos títulos por vírgula ou nova linha

### Formato Excel
Altera o formato de saída (Padrão ou Novo Programa). Mesma opção da tela principal.

### Lista de Números Processados
Clique em **Ver Lista** para abrir o arquivo `NAO_APAGAR.log` no Bloco de Notas. Este arquivo contém todos os números já processados.

### Atualizações
Clique em **Verificar Atualizações** para checar se há uma nova versão disponível. Se houver, clique em **Baixar e Instalar** — o programa fechará automaticamente, instalará a atualização e reabrirá.

---

## Arquivo de Histórico (NAO_APAGAR.log)

O programa mantém um registro de todos os números já processados no arquivo `NAO_APAGAR.log`. Este arquivo é fundamental para o funcionamento da deduplicação.

**Localização**: `%LOCALAPPDATA%\VCF_Processor_Fast\NAO_APAGAR.log`

> **Importante**: Não apague este arquivo. Ele contém o histórico de todos os contatos já exportados.

---

## Atalhos de Teclado

| Atalho | Ação |
|--------|------|
| `Ctrl +` | Aumentar zoom |
| `Ctrl -` | Diminuir zoom |
| `Ctrl 0` | Resetar zoom |

---

## Redimensionar a Janela

Arraste as bordas ou cantos da janela para redimensioná-la. A janela não tem barra de título padrão — arraste pela barra superior para mover.

---

## Solução de Problemas

**O programa não abre após a instalação**
- Verifique se o Windows Defender não bloqueou o executável
- Tente executar como administrador

**O arquivo Excel não é gerado**
- Verifique se você tem permissão de escrita na pasta do arquivo VCF
- O arquivo será salvo na mesma pasta do VCF de entrada

**"Erro ao verificar atualizações"**
- Verifique sua conexão com a internet
- O programa usa um proxy na porta 1090 — certifique-se de que está ativo

**Os números processados sumiram**
- Verifique se o arquivo `NAO_APAGAR.log` existe em `%LOCALAPPDATA%\VCF_Processor_Fast\`
- O programa tem fallbacks automáticos para outras localizações se não conseguir escrever na pasta principal

---

## Publicar Nova Versão (Para Desenvolvedores)

```cmd
python create_release.py 2.9.XX
```

Isso compila o app, cria o instalador e publica automaticamente no Google Drive.
