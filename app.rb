# # load ENV variables from .env file if it exists
env_file =  File.expand_path("../.env", __FILE__)
if File.exist?(env_file)
  require 'dotenv'
  Dotenv.load! env_file
end

# load ENV variables from container environment if json file exists
# see https://github.com/phusion/baseimage-docker#envvar_dumps
env_json_file = "/etc/container_environment.json"
if File.exist?(env_json_file)
  env_vars = JSON.parse(File.read(env_json_file))
  env_vars.each { |k, v| ENV[k] = v }
end

# required ENV variables, can be set in .env file
ENV['RACK_ENV'] ||= "development"
ENV['ES_HOST'] ||= "elasticsearch:9200"
ENV["ELASTIC_SEARCH"] ||= "http://elasticsearch:9200"

require 'active_support/all'
require 'sinatra'
require 'sinatra/custom_logger'
require 'semantic_logger'
require 'json'
require 'elasticsearch'
require 'jbuilder'

Dir[File.join(File.dirname(__FILE__), 'lib', '*.rb')].each { |f| require f }

configure do
  register Sinatra::CustomLogger
  SemanticLogger.default_level = :info
  SemanticLogger.add_appender(io: $stdout)
  logger = SemanticLogger['TestLogger']

  # Send write calls to #info
  logger.instance_eval do
    def write(str)
      info(str)
    end
  end

  set :raise_errors, true
  set :logger, logger
  use Rack::CommonLogger, logger
end

set :client, Elasticsearch::Client.new(host: ENV['ES_HOST'], user: "elastic", password: ENV['ELASTIC_PASSWORD'])

# Work around rack protection referrer bug
set :protection, :except => :json_csrf
set :default_size, 20
set :accepted_params, %w(query page filter query.name query.names query.local)
set :filter_types, %w(location type)
set :accepted_filter_param_values, %w(country.country_code types country.country_name)
set :json_builder, Jbuilder.new
set :id_uri_prefix, "https://"
set :id_prefix, "ror.org"

def search_all(start = 0, size = settings.default_size)
  settings.client.search from: start, size: size
end

def simple_query(term)
  settings.json_builder.query_string do
    settings.json_builder.query term
  end

end

def match_field(field, term)
  settings.json_builder.match do
    settings.json_builder.set! field do
      settings.json_builder.query term
      settings.json_builder.operator "and"
    end
  end
end

def multi_field_match(fields, term)
  settings.json_builder.multi_match do
    settings.json_builder.query term
    settings.json_builder.operator "and"
    settings.json_builder.fields fields
  end
end


def gen_filter_query(query,filter)
  filter = filter.split(",")
  new_query = {}
  new_query[:query] = {:bool => {:must => query["query"]}}
  filter_hsh = {}
  filter_hsh[:filter] = []
  filter.each { |f|
    field,term = f.split(":")
    filter_hsh[:filter] << {:match => {"#{field}" => term}}
  }
  new_query[:query][:bool].merge!(filter_hsh)

  new_query
end

# meta program so that one can build query strings depending on parameter
def generate_query(options = {})
  filter = nil
  qt = nil
  if options["filter"]
    filter = options["filter"].split(",")
  end
  q = settings.json_builder.search do
        settings.json_builder.query do
          if options.key?("query")
            simple_query(options["query"])
          elsif options.key?("query.local")
            match_field("local",options["query.local"])
          elsif options.key?("query.name")
            match_field("name",options["query.name"])
          elsif options.key?("query.names")
            fields = %w[ name aliases acronyms labels.label ]
            multi_field_match(fields, options["query.names"])
          end
        end
      end
end

def process (options = {})
  msg = nil
  query = generate_query(options)
  if options["page"]
    pg = options["page"].to_i
    if (pg.is_a? Integer and pg > 0)
      msg = paginate(pg,query)
    else
      msg = {:error => "page parameter: #{options['page']} must be an Integer."}
    end
  else
    query = gen_filter_query(query,options["filter"]) if options["filter"]
    msg = find(query)
  end
  msg
end

def find (query = nil, start = 0, size = settings.default_size)
  if query.nil?
    search_all
  else
    settings.client.search body: query, from: start, size: size
  end
end

def search_by_id (id)
  settings.client.get_source index: 'org-id-grid', id: id
end

def paginate (page, query = nil)
  start = settings.default_size * (page - 1)
  find(query, start)
end

def check_params
  content_type "application/json"
  bad_param_msg = {}
  bad_param_msg[:illegal_parameter] = []
  bad_param_msg[:illegal_parameter_values] = []
  params.keys.each { |k|
    unless settings.accepted_params.include?(k)
      bad_param_msg[:illegal_parameter] << k
    end
  }
  if params["filter"]
    filter = params["filter"].split(",")
    get_param_values = filter.map { |f| f.split(":")[0]}
    get_param_values.map { |p|
      unless settings.accepted_filter_param_values.include?(p)
        bad_param_msg[:illegal_parameter_values] << p
      end
    }
  end
  bad_param_msg
end

def process_id(id)
  valid_id = nil
  check_id = id.split("/")
  id_components = []
  check_id.each { |i|
    id_components << i if i == settings.id_prefix || i =~ /\w{8}/
  }

  valid_id = "#{settings.id_uri_prefix}#{id_components.join("/")}" if id_components.count == 2

  valid_id
end

def process_results
  results = {}
  errors = []
  msg = process(params)
  if msg.has_key? (:error)
    errors << msg
  else
    results["number of results"] = nil
    results["time taken"] = nil
    results["hits"] = []
    results["number of results"] = msg["hits"]["total"]
    results["time taken"] = msg["took"]
    msg["hits"]["hits"].each { |result|
      results ["hits"] << result["_source"]
    }
  end
  [results,errors]
end

after do
  response.headers['Access-Control-Allow-Origin'] = '*'
end

get '/organizations' do
  content_type "application/json"
  bad_params = {}
  bad_params = check_params
  msg = nil
  results = {}
  errors = []
  info = {}
  if bad_params.values.flatten.empty?
    results,errors = process_results
    info = errors.empty? ? results : errors
    JSON.pretty_generate info
  else
    JSON.pretty_generate bad_params
  end
end

get %r{/organizations/(.*?ror.*)} do |id|
  valid_id = process_id(id)
  msg = {}
  content_type "application/json"
  if valid_id
    msg = search_by_id(valid_id)
  else
    msg = {:error => "Expect id with the prefix ror.org"}
  end
  JSON.pretty_generate msg
end

get '/heartbeat' do
  content_type 'text/html'

  'OK'
end
