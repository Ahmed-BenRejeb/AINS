{{- define "sentinel.labels" -}}
app.kubernetes.io/part-of: sentinel
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
