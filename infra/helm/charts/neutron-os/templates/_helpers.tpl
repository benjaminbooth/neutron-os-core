{{/*
NeutronOS Helm Chart Helpers
Extracted and adapted from docs/_tools/publisher/deploy/helm/publisher/
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "neutron-os.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "neutron-os.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "neutron-os.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "neutron-os.labels" -}}
helm.sh/chart: {{ include "neutron-os.chart" . }}
{{ include "neutron-os.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "neutron-os.selectorLabels" -}}
app.kubernetes.io/name: {{ include "neutron-os.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Sense selector labels
*/}}
{{- define "neutron-os.signalSelectorLabels" -}}
{{ include "neutron-os.selectorLabels" . }}
app.kubernetes.io/component: sense
{{- end }}

{{/*
API selector labels
*/}}
{{- define "neutron-os.apiSelectorLabels" -}}
{{ include "neutron-os.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "neutron-os.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "neutron-os.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database URL helper
*/}}
{{- define "neutron-os.databaseUrl" -}}
{{- if .Values.postgresql.enabled }}
postgresql://{{ .Values.postgresql.auth.username }}:{{ .Values.postgresql.auth.password }}@{{ include "neutron-os.fullname" . }}-postgresql:5432/{{ .Values.postgresql.auth.database }}
{{- else }}
postgresql://{{ .Values.externalDatabase.username }}@{{ .Values.externalDatabase.host }}:{{ .Values.externalDatabase.port }}/{{ .Values.externalDatabase.database }}
{{- end }}
{{- end }}
