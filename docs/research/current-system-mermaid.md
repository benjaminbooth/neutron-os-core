# Neutron OS Diagrams - Mermaid Format

These diagrams render in GitHub, GitLab, and VS Code (with Mermaid extension).

---

## 1. Current System (As-Built)

```mermaid
flowchart TB
    subgraph NETL["NETL TRIGA Reactor"]
        sensors["Sensors & DAQ"]
        csv["CSV Data Files"]
    end
    
    subgraph TACC["TACC Lonestar6"]
        storage["HPC Storage"]
        compute["Compute Nodes"]
    end
    
    subgraph Box["UT Box"]
        boxsync["Synced Data"]
    end
    
    subgraph Local["Local Dev"]
        python["Python Scripts"]
        plotly["Plotly Dashboards"]
        jupyter["Jupyter Notebooks"]
    end
    
    sensors --> csv
    csv --> boxsync
    csv --> storage
    storage --> compute
    boxsync --> python
    compute --> python
    python --> plotly
    python --> jupyter
    
    style NETL fill:#e1f5fe,color:#000000
    style TACC fill:#fff3e0,color:#000000
    style Box fill:#e8f5e9,color:#000000
    style Local fill:#fce4ec,color:#000000
linkStyle default stroke:#777777,stroke-width:3px
```

---

## 2. MVP Target Architecture

```mermaid
flowchart TB
    subgraph Sources["Data Sources"]
        netl["NETL TRIGA<br/>Sensors/CSV"]
        mpact["MPACT/SAM<br/>Simulations"]
        opslog["Ops Log<br/>Entries"]
    end
    
    subgraph Platform["Neutron OS Platform"]
        subgraph Ingest["Ingestion"]
            csv_loader["CSV Loader"]
            hdf5_parser["HDF5 Parser"]
            api["REST API"]
        end
        
        subgraph Storage["Lakehouse"]
            bronze["Bronze<br/>(Raw)"]
            silver["Silver<br/>(Cleaned)"]
            gold["Gold<br/>(Analytics)"]
        end
        
        subgraph Transform["dbt Transforms"]
            dbt["dbt-core"]
        end
    end
    
    subgraph Consume["Consumption"]
        superset["Apache Superset"]
        plotly2["Plotly/Dash"]
        notebook["Jupyter"]
    end
    
    netl --> csv_loader
    mpact --> hdf5_parser
    opslog --> api
    
    csv_loader --> bronze
    hdf5_parser --> bronze
    api --> bronze
    
    bronze --> dbt
    dbt --> silver
    silver --> dbt
    dbt --> gold
    
    gold --> superset
    gold --> plotly2
    silver --> notebook
    
    style Sources fill:#e3f2fd,color:#000000
    style Platform fill:#f3e5f5,color:#000000
    style Consume fill:#e8f5e9,color:#000000
linkStyle default stroke:#777777,stroke-width:3px
```

---

## 3. Data Flow: Measured vs Modeled

```mermaid
flowchart LR
    subgraph Measured["Measured Data"]
        sensor["Sensor Reading<br/>source='measured'"]
    end
    
    subgraph Modeled["Modeled Data"]  
        sim["DT Prediction<br/>source='modeled'"]
    end
    
    subgraph Silver["Silver Layer"]
        readings["reactor_readings<br/>(unified)"]
    end
    
    subgraph Dashboard["Dashboard"]
        viz["Side-by-side<br/>Comparison"]
    end
    
    sensor --> readings
    sim --> readings
    readings --> viz
    
    style Measured fill:#c8e6c9,color:#000000
    style Modeled fill:#ffecb3,color:#000000
linkStyle default stroke:#777777,stroke-width:3px
```

---

## 4. Development Phases

```mermaid
gantt
    title Neutron OS Development Roadmap
    dateFormat  YYYY-MM
    
    section Phase 1: Foundation
    Iceberg Lakehouse Setup     :done, p1a, 2026-01, 2026-02
    CSV Ingest Pipeline         :done, p1b, 2026-01, 2026-02
    Basic Superset Dashboards   :active, p1c, 2026-02, 2026-03
    
    section Phase 2: Core Platform
    dbt Transforms (Silver/Gold) :p2a, 2026-03, 2026-04
    Electronic Logbook API       :p2b, 2026-03, 2026-05
    Audit Trail Tables           :p2c, 2026-04, 2026-05
    
    section Phase 3: DT Integration
    MPACT Output Parser          :p3a, 2026-05, 2026-06
    ML Training Pipeline         :p3b, 2026-06, 2026-08
    Offline Predictions          :p3c, 2026-07, 2026-09
    
    section Phase 4: Real-Time
    Streaming Ingest             :p4a, 2026-09, 2026-11
    Live Prediction Dashboard    :p4b, 2026-10, 2026-12
```

---

## 5. Component Dependencies

```mermaid
graph TD
    subgraph Foundation["Phase 1: Foundation"]
        iceberg["Apache Iceberg"]
        duckdb["DuckDB"]
        bronze["Bronze Layer"]
    end
    
    subgraph Core["Phase 2: Core"]
        dbt["dbt-core"]
        silver["Silver Layer"]
        gold["Gold Layer"]
        logservice["Log Service"]
    end
    
    subgraph DT["Phase 3: Digital Twin"]
        ml["ML Pipeline"]
        surrogates["Surrogate Models"]
        validation["Validation Engine"]
    end
    
    subgraph RT["Phase 4: Real-Time"]
        streaming["Streaming Ingest"]
        inference["Real-Time Inference"]
        alerts["Operator Alerts"]
    end
    
    iceberg --> bronze
    duckdb --> bronze
    bronze --> dbt
    dbt --> silver
    dbt --> gold
    
    silver --> ml
    gold --> ml
    ml --> surrogates
    surrogates --> validation
    
    bronze --> streaming
    surrogates --> inference
    validation --> alerts
    
    style Foundation fill:#e8f5e9,color:#000000
    style Core fill:#e3f2fd,color:#000000
    style DT fill:#fff3e0,color:#000000
    style RT fill:#fce4ec,color:#000000
linkStyle default stroke:#777777,stroke-width:3px
```

---

## 6. Multi-Tenant Architecture

```mermaid
flowchart TB
    subgraph Platform["Neutron OS Platform"]
        subgraph UTAustin["UT Austin (org_id: ut_netl)"]
            triga["TRIGA DT"]
            msr["MSR DT"]
            offgas["OffGas DT"]
        end
        
        subgraph Future["Future Partners"]
            partner1["Partner Org 1"]
            partner2["Partner Org 2"]
        end
        
        subgraph Shared["Shared Infrastructure"]
            api2["APIs"]
            storage2["Lakehouse"]
            compute2["Compute"]
        end
    end
    
    triga --> storage2
    msr --> storage2
    offgas --> storage2
    partner1 -.-> storage2
    partner2 -.-> storage2
    
    storage2 --> api2
    
    style UTAustin fill:#e8f5e9,color:#000000
    style Future fill:#f5f5f5,stroke-dasharray: 5 5,color:#000000
    style Shared fill:#e3f2fd,color:#000000
linkStyle default stroke:#777777,stroke-width:3px
```

---

## 7. Prediction Uncertainty Over Time

```mermaid
xychart-beta
    title "Prediction Confidence Between Sensor Readings"
    x-axis [0ms, 25ms, 50ms, 75ms, 100ms]
    y-axis "Confidence %" 0 --> 100
    line "Confidence" [100, 85, 70, 60, 100]
    linkStyle default stroke:#777777,stroke-width:3px
```

---

## Usage Notes

### Rendering
- **GitHub/GitLab**: Renders automatically in markdown preview
- **VS Code**: Install "Markdown Preview Mermaid Support" extension
- **Export to PNG/SVG**: Use mermaid CLI (`mmdc`) or online editor at mermaid.live

### Editing
- Live editor: https://mermaid.live
- Syntax docs: https://mermaid.js.org/syntax/flowchart.html

### Converting to Images for Word
```bash
# Install mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Convert to PNG
mmdc -i diagram.mmd -o diagram.png -b transparent

# Convert to SVG (better for scaling)
mmdc -i diagram.mmd -o diagram.svg
```
