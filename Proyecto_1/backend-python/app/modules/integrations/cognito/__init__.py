"""Adaptador de la API de Amazon Cognito user pools (PRO-14).

Solo operaciones públicas del cliente sin secreto: SignUp, ConfirmSignUp,
InitiateAuth (USER_PASSWORD_AUTH), UpdateUserAttributes y GetUser. Cognito no
evalúa IAM en ellas; no se necesitan credenciales AWS, pero sí salida a
``cognito-idp.<región>.amazonaws.com``. Detalle: docs/api/python-auth.md.
"""
