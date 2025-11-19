pipeline {
    agent any

    environment {
        PYTHON = 'python3'
        VENV = "${WORKSPACE}/venv"
        DJANGO_SETTINGS_MODULE = 'uniconnect.settings_auth'
    }

    options {
        skipStagesAfterUnstable()
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set up Python') {
            steps {
                sh '''
                    set -e
                    ${PYTHON} -m venv ${VENV}
                    . ${VENV}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Django checks (Auth)') {
            steps {
                sh '''
                    set -e
                    . ${VENV}/bin/activate
                    python manage.py check --settings=${DJANGO_SETTINGS_MODULE}
                '''
            }
        }

        stage('Build auth-service image') {
            steps {
                sh '''
                    set -e
                    docker build -f services/auth_service/Dockerfile -t auth-service:latest .
                '''
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
