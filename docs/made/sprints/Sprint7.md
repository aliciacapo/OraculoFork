# SPRINT 7: GERENCIAMENTO DE TOKEN - PARTE 2

13/11/2025 -- 19/11/2025

## Dados do Sprint
* **Goal**:  13/11/2025 -- 19/11/2025
* **Data Início**: 2025-11-13
* **Data Fim**: 2025-11-19
* **Status**: PLANNED
## Sprint Backlog

|Nome |Descrição|Resposável |Data de Inicio Planejada| Data de Entrega Planejada| Data de Inicío | Data Entrega | Status|
|:----|:---------|:-------- |:----------------------:| :-----------------------:| :------------: |:------------:|:-----:|
|Implementar criptografia|Criptografar tokens antes de salvar|aliciacapo|2025-11-13|2025-11-13|2025-11-13|2025-11-19|TODO|
|Camada de armazenamento|Persistir tokens criptografados|aliciacapo|2025-11-13|2025-11-13|2025-11-13|2025-11-19|TODO|
     
## Gantt 

```mermaid
gantt
    dateFormat YYYY-MM-DD
    axisFormat %d/%m


    section Sprint - Sprint 7: Gerenciamento de Token - Parte 2
    Implementar criptografia (Real) :done, Implementar criptografia_actual, 2025-11-12, 2025-11-18
    Camada de armazenamento (Real) :done, Camada de armazenamento_actual, 2025-11-12, 2025-11-18
```

# Análise de Dependências do Sprint

Análise gerada em: 10/11/2025, 10:17:42

## 🔍 Grafo de Dependências

```mermaid
graph BT
    classDef sprint fill:#a8e6cf,stroke:#333,stroke-width:2px;
    classDef done fill:#98fb98,stroke:#333,stroke-width:2px;
    classDef external fill:#ffd3b6,stroke:#333,stroke-width:1px;
    feature2_token.securestorage.implementencryption["📝 Tarefa: Implementar criptografia<br>📊 Estado: TODO<br>👤 Responsável: aliciacapo"]:::sprint
    feature2_token.securestorage.storagelayer["📝 Tarefa: Camada de armazenamento<br>📊 Estado: TODO<br>👤 Responsável: aliciacapo"]:::sprint
```

**Legenda:**
- 🟢 Verde Claro: Issues no sprint
- 🟢 Verde Escuro: Issues concluídas
- 🟡 Laranja: Dependências externas ao sprint
- ➡️ Linha sólida: Dependência no sprint
- ➡️ Linha pontilhada: Dependência externa

## 📋 Sugestão de Execução das Issues

| # | Título | Status | Responsável | Dependências |
|---|--------|--------|-------------|---------------|
| 1 | Implementar criptografia | TODO | aliciacapo | 🆓 |
| 2 | Camada de armazenamento | TODO | aliciacapo | 🆓 |

**Legenda das Dependências:**
- 🆓 Sem dependências
- ✅ Issue concluída
- ⚠️ Dependência externa ao sprint

            
## Cumulative Flow
![ Cumulative Flow](./charts/cfd-Sprint7.svg)

## Throughput
![ Throughput](./charts/throuput-Sprint7.svg)
        

        