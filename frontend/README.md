# Frontend

React + Vite + TypeScript web application for Neutron OS.

## Status

**Stub** - Will be implemented in later phases.

## Technology Stack

| Technology | Purpose |
|------------|---------|
| React 18+ | UI framework |
| Vite | Build tool |
| TypeScript | Type safety |
| TanStack Query | Data fetching |
| TanStack Router | Routing |
| Tailwind CSS | Styling |
| Shadcn/ui | Component library |

## Planned Features

| Module | Description |
|--------|-------------|
| Dashboard | Reactor overview, status |
| Simulator | Interactive reactor simulation |
| Ops Log | Operations log viewer/editor |
| Experiments | Experiment tracking |
| Analytics | Self-service data exploration |
| Audit | Audit trail viewer, evidence export |
| Admin | User management, settings |

## Structure (Planned)

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/        # Shared UI components
│   ├── features/          # Feature modules
│   │   ├── dashboard/
│   │   ├── simulator/
│   │   ├── ops-log/
│   │   ├── experiments/
│   │   ├── analytics/
│   │   └── audit/
│   ├── services/          # API client layer
│   ├── stores/            # State management
│   └── utils/
└── tests/
```

## Relationship to TRIGA DMSRI

This frontend will incorporate and improve upon features from the existing TRIGA DMSRI Flask app (`triga_dt_website`). The Flask app may continue to run during transition, with new features built in this React app.
