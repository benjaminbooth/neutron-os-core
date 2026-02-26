{{/*
Expand the name of the chart.
*/}}
{{- define "docflow.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "docflow.fullname" -}}
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
{{- define "docflow.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "docflow.labels" -}}
helm.sh/chart: {{ include "docflow.chart" . }}
{{ include "docflow.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "docflow.selectorLabels" -}}
app.kubernetes.io/name: {{ include "docflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API selector labels
*/}}
{{- define "docflow.apiSelectorLabels" -}}
{{ include "docflow.selectorLabels" . }}
app.kubernetes.io/component: api
{{- if .Values.blueGreen.enabled }}
docflow.io/color: {{ .Values.blueGreen.activeColor }}
{{- end }}
{{- end }}

{{/*
Agent selector labels
*/}}
{{- define "docflow.agentSelectorLabels" -}}
{{ include "docflow.selectorLabels" . }}
app.kubernetes.io/component: agent
{{- if .Values.blueGreen.enabled }}
docflow.io/color: {{ .Values.blueGreen.activeColor }}
{{- end }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "docflow.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "docflow.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database URL construction
*/}}
{{- define "docflow.databaseUrl" -}}
{{- if .Values.externalDatabase.enabled }}
{{- printf "postgresql://%s:%s@%s:%d/%s" .Values.externalDatabase.user .Values.externalDatabase.password .Values.externalDatabase.host (.Values.externalDatabase.port | int) .Values.externalDatabase.database }}
{{- else }}
{{- printf "postgresql://docflow:docflow@%s-postgresql:5432/docflow" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Redis URL construction
*/}}
{{- define "docflow.redisUrl" -}}
{{- if .Values.externalRedis.enabled }}
{{- printf "redis://%s:%d" .Values.externalRedis.host (.Values.externalRedis.port | int) }}
{{- else }}
{{- printf "redis://%s-redis-master:6379" .Release.Name }}
{{- end }}
{{- end }}
