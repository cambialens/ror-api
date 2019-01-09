FROM phusion/passenger-full:rel-1.0.1
MAINTAINER Martin Fenner "mfenner@datacite.org"

# Set correct environment variables
ENV HOME /home/app
ENV DOCKERIZE_VERSION v0.6.0

# Allow app user to read /etc/container_environment
RUN usermod -a -G docker_env app

# Use baseimage-docker's init process
CMD ["/sbin/my_init"]

# Install Ruby 2.4.4
RUN bash -lc 'rvm --default use ruby-2.4.4'

# Update installed APT packages, clean up when done
RUN apt-get update && \
    apt-get upgrade -y -o Dpkg::Options::="--force-confold" && \
    apt-get clean && \
    apt-get install ntp wget unzip tzdata -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Enable Passenger and Nginx and remove the default site
# Preserve env variables for nginx
RUN rm -f /etc/service/nginx/down && \
    rm /etc/nginx/sites-enabled/default
COPY vendor/docker/webapp.conf /etc/nginx/sites-enabled/webapp.conf
COPY vendor/docker/00_app_env.conf /etc/nginx/conf.d/00_app_env.conf

# Use Amazon NTP servers
COPY vendor/docker/ntp.conf /etc/ntp.conf

# enable SSH
RUN rm -f /etc/service/sshd/down

# Install dockerize
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz && \
    tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

# Copy webapp folder
COPY . /home/app/webapp/
RUN mkdir -p /home/app/webapp/vendor/bundle && \
    chown -R app:app /home/app/webapp && \
    chmod -R 755 /home/app/webapp

# Install Ruby gems
WORKDIR /home/app/webapp
RUN gem update --system && \
    gem install bundler && \
    /sbin/setuser app bundle install --path vendor/bundle

# install custom ssh key during startup
RUN mkdir -p /etc/my_init.d
COPY vendor/docker/10_ssh.sh /etc/my_init.d/10_ssh.sh

# Expose web
EXPOSE 80
