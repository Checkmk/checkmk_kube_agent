{{/*
Expand the name of the chart.
*/}}
{{- define "checkmk.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "checkmk.fullname" -}}
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
{{- define "checkmk.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "checkmk.labels" -}}
helm.sh/chart: {{ include "checkmk.chart" . }}
{{ include "checkmk.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "checkmk.selectorLabels" -}}
app.kubernetes.io/name: {{ include "checkmk.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service accounts
*/}}
{{- define "checkmk.serviceAccountName.checkmk" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (print (include "checkmk.fullname" .) "-checkmk") .Values.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{- define "checkmk.serviceAccountName.clusterCollector" -}}
{{- if .Values.clusterCollector.serviceAccount.create -}}
    {{ default (print (include "checkmk.fullname" .) "-cluster-collector") .Values.clusterCollector.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.clusterCollector.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{- define "checkmk.serviceAccountName.nodeCollector.containerMetricsCollector" -}}
{{- if .Values.nodeCollector.containerMetricsCollector.serviceAccount.create -}}
    {{ default (print (include "checkmk.fullname" .) "-node-collector-container-metrics") .Values.nodeCollector.containerMetricsCollector.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.nodeCollector.containerMetricsCollector.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{- define "checkmk.serviceAccountName.nodeCollector.machineSectionsCollector" -}}
{{- if .Values.nodeCollector.machineSectionsCollector.serviceAccount.create -}}
    {{ default (print (include "checkmk.fullname" .) "-node-collector-machine-sections") .Values.nodeCollector.machineSectionsCollector.serviceAccount.name }}
{{- else -}}
    {{ default "default" .Values.nodeCollector.machineSectionsCollector.serviceAccount.name }}
{{- end -}}
{{- end -}}